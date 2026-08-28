import os

from dto.dto_tools import DTOTool
from dto.enums import ToolOperation
from tools.ATool import ATool
from tools.errors import ToolError
from tools.app.tool_read_file import ToolReadFile


class ToolReadMultiplyFiles(ATool):
    @staticmethod
    def get_description() -> dict:
        return {
            "description": "Read the contents of multiple files from the same directory in a single operation. Returns each file's content with clear separation. Use this tool when you need to examine 2 or more files at once — it is more efficient than multiple individual read_file calls. All files must be in the same directory specified by root_path.",
            "parameters": {
                "type": "object",
                "required": ["root_path", "file_name"],
                "properties": {
                    "root_path": {
                        "type": "string",
                        "description": "Parent directory of the files"
                    },
                    "file_name": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file names to read"
                    }
                }
            }
        }

    @staticmethod
    def get_parameters() -> dict:
        return {}

    def exec(self, root_path: str, file_name: list) -> DTOTool:
        results = []
        file_paths = []
        tool_read = ToolReadFile(project=self.project)
        for name in file_name:
            file_path = os.path.join(root_path, name)
            header = f"--- file: {file_path} ---"

            if root_path:
                real_file = os.path.realpath(os.path.join(self.project_root, file_path))
                real_root = os.path.realpath(os.path.join(self.project_root, root_path))
                if not (real_file.startswith(real_root + os.sep) or real_file == real_root):
                    results.append(f"{header}\ninvalid path of /{name}")
                    continue

            file_paths.append(name)
            try:
                single_result = tool_read.exec(path=file_path)
                results.append(f"{header}\n{single_result.result}")
            except ToolError:
                results.append(f"{header}\ninvalid path of /{name}")

        return DTOTool(
            result="\n\n".join(results),
            tool_name='read_multiply_files',
            file_path="\n".join(file_paths),
            operation=ToolOperation.READ,
        )