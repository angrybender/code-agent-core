from dto.dto_tools import DTOTool
from dto.enums import ToolOperation
from tools.ATool import ATool
from tools.errors import ToolError


class ToolReadFile(ATool):
    @staticmethod
    def get_description() -> dict:
        return {
            "description": "Read file by path and return its content. Use `offset` and `limit` parameters for large files to avoid loading the entire file into context. Prefer `search_file` when you don't know the exact file location or need to find specific code patterns. For discovering what files exist in a directory, use `list_in_directory` instead.",
            "parameters": {
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "path to file"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Start reading from line number N (0-based). Default: 0"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to return. If not specified, returns all lines from offset to end of file"
                    }
                }
            }
    }

    def exec(self, path: str, offset: int = 0, limit: int = None) -> DTOTool:
        if not self._validate_path(path):
            raise ToolError('Invalid path')
        content = self.project.read_file(path)

        if content['error']:
            result = content['error']
            result = result.replace(self.project_root, '')
            raise ToolError(result)

        full_content = content['content']
        lines = full_content.split('\n')
        lines = lines[offset:]
        if limit is not None:
            lines = lines[:limit]
        result = '\n'.join(lines)

        return DTOTool(
            result=result,
            operation=ToolOperation.READ,
            tool_name='read',
            file_path=path,
        )