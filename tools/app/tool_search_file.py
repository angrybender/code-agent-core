from dto.dto_tools import DTOTool
from tools.ATool import ATool
from tools.errors import ToolError


class ToolSearchFile(ATool):
    def exec(self, needle, extension=None) -> DTOTool:
        needle = str(needle).strip()
        if not needle:
            raise ToolError('Needle must be a non-empty string')

        total_count, results = self.project.search_files(needle, str(extension))
        if not results:
            return DTOTool(
                result='No matches found.',
                tool_name='search_file',
                output='Found: 0 file(s)',
            )

        formatted_result = []
        for result in results:
            formatted_result.append(
                f"file: `{result['file']}`\nline: {result['line_number']}\nfound line: ```{result['found']}```"
            )

        return DTOTool(
            result='\n\n'.join(formatted_result),
            tool_name='search_file',
            output=f'Found: {total_count} file(s)',
        )