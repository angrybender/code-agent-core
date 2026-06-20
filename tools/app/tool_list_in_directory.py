import os

from dto.dto_tools import DTOTool
from path_helper import ls_la
from tools.ATool import ATool
from tools.errors import ToolError


class ToolListInDirectory(ATool):
    @staticmethod
    def get_description() -> dict:
        return {
            "description": "List files and directories from a path.\nResult contains a list of files and directories (only first level); directory names end with the symbol `/`.\nUse to discover project structure and find relevant files or directories. For searching code content across files, use `search_file` instead. For reading a known file, use `read_file` directly.",
            "parameters": {
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "path, for the root of the project use `.`"
                    }
                }
            }
        }

    def exec(self, path) -> DTOTool:
        if not self._validate_path(path):
            raise ToolError('Invalid path')
        absolute_path = os.path.join(self.project_root, path)

        if not os.path.exists(absolute_path):
            raise ToolError('Path not exists')

        if not os.path.isdir(absolute_path):
            raise ToolError('This is a file, use read file tool')

        result = ls_la(str(absolute_path))
        result = [_['line'] for _ in result]

        return DTOTool(
            result="\n".join(result),
            tool_name='list_in_directory'
        )