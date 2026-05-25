from dto.dto_tools import DTOTool
from dto.enums import ToolOperation
from tools.ATool import ATool
from tools.errors import ToolError


class ToolReadFile(ATool):
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