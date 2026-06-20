import json

from dto.dto_tools import DTOTool
from dto.enums import ToolOperation
from tools.ATool import ATool
from tools.errors import ToolError


class ToolWriteFile(ATool):
    @staticmethod
    def get_description() -> dict:
        return {
            "description": "Write full data to a file.\nUse this command ONLY if:\n1. You are editing a file with fewer than 100 lines.\n2. You are creating a new file.",
            "parameters": {
                "type": "object",
                "required": ["path", "content"],
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "path to file"
                    },
                    "content": {
                        "type": "string",
                        "description": "Data to write to the file. Don't escape quotes (\") and brackets (< >)"
                    }
                }
            }
        }

    def _correction_write_arg(self, value) -> str:
        if type(value) is dict or type(value) is list:
            value = json.dumps(value, ensure_ascii=False, indent=4)
        return value

    def exec(self, path, content) -> DTOTool:
        if not self._validate_path(path):
            raise ToolError('Invalid path')

        try:
            file_is_exists = self.project.read_file(path)
            is_exist = not file_is_exists['error']
        except ToolError:
            is_exist = False

        content = self._correction_write_arg(content)
        if type(content) is not str:
            raise ToolError('File content must be string!')

        content = content.strip()
        result = self.project.write_file(path, content)

        if result['error']:
            raise ToolError(result['error'])

        return DTOTool(
            result="True",
            tool_name="write",
            file_path=str(path),
            operation=ToolOperation.UPDATE if is_exist else ToolOperation.CREATE,
            meta={
                'file_name': path
            }
        )