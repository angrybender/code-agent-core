import shlex

from mcp_integration.client import MCP


class MCPToolExecutor:
    """Adapter that calls MCP server tools and formats responses for agent conversation context."""

    def __init__(self, server_name: str, mcp_config: dict):
        """
        :param server_name: Name of the MCP server (e.g. 'mcp_browser')
        :param mcp_config: Config dict from parse_agent_commands(..., 'mcp'), includes 'config' sub-dict and 'cmd' field
        """
        self.server_name = server_name
        self.mcp_config = mcp_config

        config = self.mcp_config.get('config', {})
        transport = config.get('type', 'cli')
        cmd_str = self.mcp_config.get('cmd', '')
        parts = shlex.split(cmd_str) if cmd_str else []
        command = parts[0] if parts else None
        args = parts[1:] if len(parts) > 1 else []
        url = config.get('url')
        self.client = MCP(transport=transport, url=url, command=command, args=args)

    def list_tools(self) -> list:
        """List available tools from the MCP server."""
        return self.client.list_tools()

    def call_tool(self, tool_name: str, args: dict = None) -> dict:
        """
        Call a tool on the MCP server.
        
        :param tool_name: Tool name, possibly prefixed with 'mcp:'
        :param args: Arguments to pass to the tool
        :return: Result dict with 'result', 'tool_name' and optional 'error' keys
        """
        real_name = tool_name.removeprefix("mcp:")
        try:
            result = self.client.call_tool(real_name, args or {})
            if "error" in result:
                return {"result": f"ERROR: {result['error']}", "error": True, "tool_name": tool_name}
            return {"result": result.get("status", str(result)), "tool_name": tool_name}
        except Exception as e:
            return {"result": f"ERROR: {e}", "error": True, "tool_name": tool_name}

    def close_session(self):
        try:
            self.client.destroy()
        except:
            pass