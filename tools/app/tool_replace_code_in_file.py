import json

from diff_helper import PatchError, apply_patch
from dto.dto_tools import DTOTool
from dto.enums import ToolOperation
from tools.ATool import ATool
from tools.errors import ToolError


class ToolReplaceCodeInFile(ATool):
    def _correction_write_arg(self, value) -> str:
        if type(value) is dict or type(value) is list:
            value = json.dumps(value, ensure_ascii=False, indent=4)
        return value

    def exec(self, path, str_find, str_replace) -> DTOTool:
        if not self._validate_path(path):
            raise ToolError('Invalid path')

        try:
            source_file = self.project.read_file(path)
        except ToolError:
            raise ToolError('File not exist')

        if source_file['error']:
            raise ToolError('File not exist')

        source_code = source_file['content']
        source_code = [_.rstrip() for _ in source_code.split("\n")]

        str_find = self._correction_write_arg(str_find)
        str_replace = self._correction_write_arg(str_replace)

        try:
            patched_file = apply_patch("\n".join(source_code), str_find, str_replace)
        except PatchError as e:
            raise ToolError(str(e))

        result = self.project.write_file(path, patched_file.strip())
        if result['error']:
            raise ToolError(result['error'])

        return DTOTool(
            result="True",
            tool_name="write_diff",
            file_path=str(path),
            operation=ToolOperation.UPDATE,
            meta={
                'file_name': path
            }
        )