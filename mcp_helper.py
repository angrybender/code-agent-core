import asyncio
import os
import os.path

from dotenv import load_dotenv
load_dotenv()

from mcp import ClientSession
from mcp.client.sse import sse_client

# Load mode configuration - 'mcp' or 'pure'
AGENT_FILE_TOOLS = os.getenv('AGENT_FILE_TOOLS', 'mcp')

async def _tool_call_sse(path: str, name: str, args: dict = None):
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
        if not abs_path.startswith(os.path.normpath(project_path)):
            return {'error': f"File: {path_in_project} doesn't exist or can't be opened"}

        if not os.path.exists(abs_path):
            return {'error': f"File: {path_in_project} doesn't exist or can't be opened"}

        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {'status': content}

    except FileNotFoundError | PermissionError | UnicodeDecodeError:
        return {'error': f"File: {path_in_project} doesn't exist or can't be opened"}


def _write_file_pure(project_path: str, path_in_project: str, text: str) -> dict:
    abs_path = os.path.normpath(os.path.join(project_path, path_in_project))
    if not abs_path.startswith(os.path.normpath(project_path)):
        return {'error': f"Cannot write file outside project directory: {path_in_project}"}

    parent_dir = os.path.dirname(abs_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(abs_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return {'status': 'File created successfully'}

def tool_call(path: str, name: str, args: dict = None) -> dict:
    if name == 'get_file_text_by_path':
        # jetbrains'mcp truncate big files
        return _read_file_pure(args['projectPath'], args['pathInProject'])

    # Pure mode: use direct Python file operations
    if AGENT_FILE_TOOLS == 'pure':
        if name == 'create_new_file':
            return _write_file_pure(
                args['projectPath'],
                args['pathInProject'],
                args['text'],
            )
        else:
            raise Exception(f"Unknown tool: {name}")
    
    # MCP mode: use existing MCP protocol implementation
    result = asyncio.run(_tool_call_sse(path, name, args))
    if result.isError:
        return {
            'error': result.content[0].text
        }
    else:
        return {
            'status': result.content[0].text
        }