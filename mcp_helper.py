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

    async def _with_session(self, async_fn):
        """Open transport, initialize MCP session, then call async_fn(session)."""
        if self.transport == "sse":
            async with sse_client(self.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await async_fn(session)

        elif self.transport == "http":
            raise Exception("not supported yet")
            async with streamablehttp_client(self.url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await async_fn(session)

        else:  # "cli"
            server_params = StdioServerParameters(command=self.command, args=self.args)
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await async_fn(session)

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
                    "inputSchema": tool.inputSchema if isinstance(tool.inputSchema, dict) else (tool.inputSchema.model_dump() if hasattr(tool.inputSchema, "model_dump") else {}),
                }
                for tool in result.tools
            ]

        return asyncio.run(self._with_session(_list))

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

        return asyncio.run(self._with_session(_call))