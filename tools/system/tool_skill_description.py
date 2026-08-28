from dto.dto_tools import DTOTool
from tools.ATool import ATool


class ToolSkillDescription(ATool):
    @staticmethod
    def get_description() -> dict:
        return {
            "description": "Get the extended (detailed) description of a skill/commandlet by its name. Use this when you need more details about what a skill does beyond its short description shown in tool lists and guidance.",
            "parameters": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The skill name (command filename without .md extension, e.g. 'git', 'run_tests')"
                    }
                }
            }
        }

    @staticmethod
    def get_parameters() -> dict:
        return {}

    def exec(self, name) -> DTOTool:
        description = self.project.get_commandlets_description(name)
        return DTOTool(
            result=description,
            tool_name="skill_description"
        )