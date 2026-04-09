import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.stdio import stdio_client, StdioServerParameters


class MCP:
    """
    Reusable MCP client supporting SSE, Streamable HTTP, and stdio transports.

    Params:
        transport: one of 'sse', 'http', 'cli'
        url: server URL — required for 'sse' and 'http' transports
        command: executable path — required for 'cli' transport
        args: optional list of CLI arguments for 'cli' transport
    """

    SUPPORTED_TRANSPORTS = ("sse", "http", "cli")

    def __init__(self, transport: str, url: str = None, command: str = None, args: list = None):
        if transport not in self.SUPPORTED_TRANSPORTS:
            raise ValueError(f"Unsupported transport: {transport!r}. Must be one of {self.SUPPORTED_TRANSPORTS}")
        if transport in ("sse", "http") and not url:
            raise ValueError(f"'url' is required for transport {transport!r}")
        if transport == "cli" and not command:
            raise ValueError("'command' is required for transport 'cli'")

        self.transport = transport
        self.url = url
        self.command = command
        self.args = args or []

    async def _run_with_session(self, async_fn):
        if self.transport == "sse":
            transport_cm = sse_client(self.url)
            read, write = await transport_cm.__aenter__()
        elif self.transport == "http":
            raise Exception("not supported yet")
        else:
            server_params = StdioServerParameters(command=self.command, args=self.args)
            transport_cm = stdio_client(server_params)
            read, write = await transport_cm.__aenter__()

        session_cm = ClientSession(read, write)
        session = await session_cm.__aenter__()
        try:
            await session.initialize()
            return await async_fn(session)
        finally:
            session_error = None
            try:
                await session_cm.__aexit__(None, None, None)
            except Exception as exc:
                session_error = exc

            transport_error = None
            try:
                await transport_cm.__aexit__(None, None, None)
            except Exception as exc:
                transport_error = exc

            if session_error:
                raise session_error
            if transport_error:
                raise transport_error

    def _run(self, async_fn):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._run_with_session(async_fn))
        finally:
            loop.close()

    def init(self):
        """Retained for API compatibility. Sessions are created per call."""
        return

    def destroy(self):
        """Retained for API compatibility. No persistent async resources are kept."""
        return

    def list_tools(self) -> list:
        """
        Return all tools exposed by the MCP server.

        Returns:
            list of dicts: [{"name": str, "description": str, "inputSchema": dict}, ...]
        """

        async def _list(session):
            result = await session.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema['properties'] if isinstance(tool.inputSchema, dict) else (tool.inputSchema.model_dump()['properties'] if hasattr(tool.inputSchema, "model_dump") else {}),
                }
                for tool in result.tools
            ]

        return self._run(_list)

    def call_tool(self, name: str, args: dict = None) -> dict:
        """
        Call an MCP tool by name with optional arguments.

        Returns:
            {"status": str} on success
            {"error": str}  on tool-level error (result.isError is True)
        """

        async def _call(session):
            result = await session.call_tool(name, args)
            if result.isError:
                text = result.content[0].text if result.content else "unknown error"
                return {"error": text}
            text = result.content[0].text if result.content else ""
            return {"status": text}

        return self._run(_call)