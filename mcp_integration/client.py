import asyncio
import threading

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters


class MCP:
    SUPPORTED_TRANSPORTS = ("sse", "http", "cli")

    def __init__(self, transport: str, url: str = None, command: str = None, args: list = None):
        if transport not in self.SUPPORTED_TRANSPORTS:
            raise ValueError(f"Unsupported transport: {transport!r}. Supported: {self.SUPPORTED_TRANSPORTS}")
        if transport in ("sse", "http") and not url:
            raise ValueError(f"Transport {transport!r} requires 'url' parameter")
        if transport == "cli" and not command:
            raise ValueError("Transport 'cli' requires 'command' parameter")

        self.transport = transport
        self.url = url
        self.command = command
        self.args = args or []

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: ClientSession | None = None
        self._session_cm = None
        self._transport_cm = None

    def init(self):
        """Establish a persistent connection to the MCP server.

        Starts a background event loop thread and initialises the MCP session.
        Blocks until the session handshake completes (or raises on timeout/error).
        """
        if self._session is not None or self._loop is not None:
            return

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True, name="mcp-event-loop")
        self._thread.start()

        future = asyncio.run_coroutine_threadsafe(self._connect(), self._loop)
        future.result(timeout=30)

    async def _connect(self):
        """Async: open transport and create/initialise ClientSession."""
        if self.transport in ("sse", "http"):
            self._transport_cm = sse_client(self.url)
        elif self.transport == "cli":
            params = StdioServerParameters(command=self.command, args=self.args)
            self._transport_cm = stdio_client(params)
        else:
            raise ValueError(f"Unsupported transport: {self.transport!r}")

        read, write = await self._transport_cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()

    def destroy(self):
        """Close the MCP session and stop the background event loop.

        Safe to call even if init() was never called.
        """
        if self._loop is not None and (self._session is not None or self._transport_cm is not None):
            future = asyncio.run_coroutine_threadsafe(self._disconnect(), self._loop)
            try:
                future.result(timeout=15)
            except Exception:
                pass

        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread is not None:
            self._thread.join(timeout=10)

        self._session = None
        self._session_cm = None
        self._transport_cm = None
        self._loop = None
        self._thread = None

    async def _disconnect(self):
        """Async: gracefully exit session and transport context managers."""
        if self._session_cm is not None:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:
                pass
        if self._transport_cm is not None:
            try:
                await self._transport_cm.__aexit__(None, None, None)
            except Exception:
                pass

    def _ensure_session(self):
        """Lazy-init: connect on first use if init() was not called explicitly."""
        if self._session is None:
            self.init()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def list_tools(self) -> list:
        """Return a list of tools available on the connected MCP server."""
        self._ensure_session()
        future = asyncio.run_coroutine_threadsafe(self._list_tools_async(), self._loop)
        return future.result()

    async def _list_tools_async(self) -> list:
        result = await self._session.list_tools()
        tools = []
        for tool in result.tools:
            schema = tool.inputSchema
            if isinstance(schema, dict):
                properties = schema.get("properties", {})
            elif hasattr(schema, "model_dump"):
                properties = schema.model_dump().get("properties", {})
            else:
                properties = {}
            tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": properties,
            })
        return tools

    def call_tool(self, name: str, args: dict = None) -> dict:
        """Call a tool on the MCP server and return the result."""
        self._ensure_session()
        future = asyncio.run_coroutine_threadsafe(self._call_tool_async(name, args), self._loop)
        return future.result()

    async def _call_tool_async(self, name: str, args: dict = None) -> dict:
        result = await self._session.call_tool(name, args or {})
        if result.isError:
            text = result.content[0].text if result.content else "unknown error"
            return {"error": text}
        text = result.content[0].text if result.content else ""
        return {"status": text}