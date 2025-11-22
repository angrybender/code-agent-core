import asyncio
import os.path

from mcp import ClientSession
from mcp.client.sse import sse_client

async def _tool_call_sse(path: str, name: str, args: dict = None):
    async with sse_client(path) as (
            read_stream,
            write_stream,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(name, args)

def tool_call(path: str, name: str, args: dict = None) -> dict:
    if name == 'get_file_text_by_path':
        # jetbrains'mcp truncate big files
        file_path = os.path.join(args['projectPath'], args['pathInProject'])
        if not os.path.exists(file_path):
            return {
                'error': f"File: {args['pathInProject']} doesn't exist or can't be opened"
            }

        with open(file_path, 'r', encoding='utf8') as f:
            return {
                'status': f.read()
            }

    result = asyncio.run(_tool_call_sse(path, name, args))
    if result.isError:
        return {
            'error': result.content[0].text
        }
    else:
        return {
            'status': result.content[0].text
        }
