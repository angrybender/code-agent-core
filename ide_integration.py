import asyncio
import os
import json
import os.path
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Load mode configuration - 'mcp' or 'pure'
class ConfigurationService:
    AGENT_FILE_TOOLS = os.getenv('AGENT_FILE_TOOLS', 'mcp')
    IDE_MCP_HOST = None

    def refresh(self):
        if self.AGENT_FILE_TOOLS == 'mcp':
            _mimic = os.getenv('IDE_AUTODISCOVERY')
            if not _mimic:
                IDE_MCP_HOST = os.getenv('IDE_MCP_HOST')
                assert IDE_MCP_HOST, 'IDE_MCP_HOST empty'
            else:
                assert os.path.exists(_mimic), f'IDE_AUTODISCOVERY={_mimic} does not contain valid path to file'
                with open(_mimic, 'r', encoding='utf8') as f:
                    _mimic_cnfg = json.load(f)

                IDE_MCP_HOST = _mimic_cnfg.get('mcpServers', {}).get('jetbrains', {}).get('serverUrl')
                assert IDE_MCP_HOST, f'IDE_AUTODISCOVERY={_mimic} does not contain valid MCP configuration: `mcpServers.jetbrains.serverUrl`'

            self.IDE_MCP_HOST = IDE_MCP_HOST

configuration = ConfigurationService()

# discovery JetBrains MCP server:
configuration.refresh()


async def _tool_call_sse(path: str, name: str, args: dict = None):
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    async with sse_client(path) as (
            read_stream,
            write_stream,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(name, args)

def _read_file_pure(project_path: str, path_in_project: str) -> dict:
    try:
        abs_path = os.path.normpath(os.path.join(project_path, path_in_project))
        if not Path(abs_path).is_relative_to(Path(os.path.normpath(project_path))):
            return {'error': f"File: {path_in_project} doesn't exist or can't be opened"}

        if not os.path.exists(abs_path):
            return {'error': f"File: {path_in_project} doesn't exist or can't be opened"}

        if os.path.isdir(abs_path):
            return {'error': f"Path: {path_in_project} is a directory, not a file"}

        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {'status': content}

    except (FileNotFoundError, PermissionError, UnicodeDecodeError, IsADirectoryError):
        return {'error': f"File: {path_in_project} doesn't exist or can't be opened"}


def _write_file_pure(project_path: str, path_in_project: str, text: str) -> dict:
    try:
        abs_path = os.path.normpath(os.path.join(project_path, path_in_project))
        if not Path(abs_path).is_relative_to(Path(os.path.normpath(project_path))):
            return {'error': f"Cannot write file outside project directory: {path_in_project}"}

        parent_dir = os.path.dirname(abs_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(text)

        return {'status': 'File created successfully'}
    except (PermissionError, OSError) as e:
        return {'error': f"Cannot write file: {path_in_project} ({e})"}

def _test__connection(project_path: str) -> dict:
    try:
        _ = asyncio.run(_tool_call_sse(configuration.IDE_MCP_HOST, 'list_directory_tree', {
            'projectPath': project_path,
            'directoryPath': '.',
            'maxDepth': 0,
        }))
    except ExceptionGroup as e:
        base = e.exceptions[0]
        if 'All connection attempts failed' in str(base):
            return {"result": False, "error": f"Invalid MCP server url: {configuration.IDE_MCP_HOST}"}
        else:
            return {"result": False, "error": str(e)}

    return {"result": True}

def tool_call(name: str, args: dict = None) -> dict:
    configuration.refresh()
    if configuration.AGENT_FILE_TOOLS == 'mcp' and name == '__test__connection__':
        return _test__connection(args['projectPath'])

    if name == 'get_file_text_by_path':
        # jetbrains'mcp truncate big files
        return _read_file_pure(args['projectPath'], args['pathInProject'])

    # Pure mode: use direct Python file operations
    if configuration.AGENT_FILE_TOOLS == 'pure':
        if name == 'create_new_file':
            return _write_file_pure(
                args['projectPath'],
                args['pathInProject'],
                args['text'],
            )
        else:
            raise Exception(f"Unknown tool: {name}")

    # MCP mode: use existing MCP protocol implementation
    result = asyncio.run(_tool_call_sse(configuration.IDE_MCP_HOST, name, args))
    if result.isError:
        return {
            'error': result.content[0].text
        }
    else:
        return {
            'status': result.content[0].text
        }