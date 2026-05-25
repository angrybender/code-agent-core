import json

from dto.dto_tools import DTOTool
from dto.enums import ToolOperation
from tools.ATool import ATool
from tools.errors import ToolError


class ToolWriteFile(ATool):
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