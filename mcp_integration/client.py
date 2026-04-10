import asyncio
import threading

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client


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
        self._stop_event: asyncio.Event | None = None
        self._session_ready: threading.Event | None = None
        self._session_error: Exception | None = None
        self._session_future = None

    async def _run_session(self):
        self._stop_event = asyncio.Event()
        try:
            if self.transport in ("sse", "http"):
                async with sse_client(self.url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self._session = session
                        self._session_ready.set()
                        await self._stop_event.wait()
            elif self.transport == "cli":
                params = StdioServerParameters(command=self.command, args=self.args)
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self._session = session
                        self._session_ready.set()
                        await self._stop_event.wait()
            else:
                raise ValueError(f"Unsupported transport: {self.transport!r}")
        except Exception as e:
            self._session_error = e
            self._session_ready.set()
        finally:
            self._session = None

    def init(self):
        if self._session is not None or self._loop is not None:
            return

        self._session_ready = threading.Event()
        self._session_error = None

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True, name="mcp-event-loop")
        self._thread.start()

        self._session_future = asyncio.run_coroutine_threadsafe(self._run_session(), self._loop)

        if not self._session_ready.wait(timeout=30):
            raise TimeoutError("MCP session did not initialize in time")

        if self._session_error:
            raise self._session_error

    def destroy(self):
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)

        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=15)

        if self._session_future is not None and self._session_future.done():
            try:
                self._session_future.exception()
            except Exception:
                pass

        self._session = None
        self._loop = None
        self._thread = None
        self._stop_event = None
        self._session_future = None

    def _ensure_session(self):
        if self._session is None:
            self.init()

    def list_tools(self) -> list:
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