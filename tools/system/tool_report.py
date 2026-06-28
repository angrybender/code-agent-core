from dto.dto_tools import DTOTool
from dto.enums import ToolOperation
from tools.ATool import ATool


class ToolReport(ATool):
    @staticmethod
    def get_description() -> dict:
        return {
            "description": "Print a short report of your work.\nUse this command when you have completely executed the instructions and have decided to finish the work.\nInclude in your report: summary of work done, list of files analyzed/created/modified, and any issues found.",
            "parameters": {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text is a report in the Markdown format. Don't write the full content of the files — a short description is enough! Include a '## Files' section listing all files you created or modified."
                    }
                }
            }
        }

    @staticmethod
    def get_parameters() -> dict:
        return {}

    def exec(self, text) -> DTOTool:
        return DTOTool(
            result=text,
            operation=ToolOperation.REPORT,
            tool_name="report"
        )