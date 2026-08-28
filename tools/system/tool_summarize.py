from dto.dto_tools import DTOTool
from tools.ATool import ATool


class ToolSummarize(ATool):
    @staticmethod
    def get_description() -> dict:
        return {
                "description": (
                "CRITICAL: Use this tool ONLY when instructed due to context window overflow. "
                "Provide a comprehensive structured summary of all work done so far. "
                "Your summary MUST follow the required sections listed in the parameter description."
            ),
            "parameters": {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {
                        "type": "string",
                        "description": (
                            "Comprehensive work summary in Markdown. MUST include ALL of these sections:\n"
                            "## Files Read: (list each file path and key findings from it)\n"
                            "## Files Created/Modified: (list each path and what was done)\n"
                            "## Commands Run: (command name and result/output summary)\n"
                            "## Key Findings: (important values, patterns, decisions discovered)\n"
                            "## Current Status: (what has been completed)\n"
                            "## What Remains: (what still needs to be done to complete the task)"
                        )
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
            tool_name="summarize"
        )