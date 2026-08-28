from dto.dto_tools import DTOTool
from tools.ATool import ATool
from tools.errors import ToolError


class ToolSearchFile(ATool):
    @staticmethod
    def get_description() -> dict:
        return {
            "description": "Searches for `needle` across all project files using fuzzy token matching. Supports languages: PHP, JS, Java, Scala, C#, Go, Ruby, HTML, CSS, YML, bash. Returns the file path and lines that contain the most relevant match. Returns the first 10 results. Use when searching for code patterns, function names, class definitions, or usages across the project. For known file locations, use `read_file` directly. For broad file/directory discovery, use `list_in_directory` first.",
            "parameters": {
                "type": "object",
                "required": ["needle", "extension"],
                "properties": {
                    "needle": {
                        "type": "string",
                        "description": "The string to search for"
                    },
                    "extension": {
                        "type": "string",
                        "description": "File extension for filtering files to search, example: 'py' (will filter only files like '*.py'), empty string for no filtering"
                    }
                }
            }
        }

    @staticmethod
    def get_parameters() -> dict:
        return {
            'pre_output': True
        }

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