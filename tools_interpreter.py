from importlib import import_module

from dto.dto_tools import DTOTool
from dto.enums import ToolPrefixes
from project import Project
from tools.ATool import ATool
from tools.app.tool_shell import ToolShell
from tools.errors import ToolError

# TODO move to ./tools
class ToolsInterpreter:
    def __init__(self, shell_tools: dict = None, project: Project = None):
        self._shell_tools = shell_tools
        self.project = project

    def _load(self, tool_name) -> ATool:
        try:
            module, tool_name = tool_name.split('__', 1)
        except:
            raise ToolError(f"wrong tool name: `{tool_name}`, check tools list and call correct")

        python_tool_name = f"tool_{tool_name}"
        class_name = ''.join(word.capitalize() for word in python_tool_name.split('_'))

        try:
            module_obj = import_module(f"tools.{module}.{python_tool_name}")
        except ModuleNotFoundError:
            raise ToolError(f"wrong tool name: `{tool_name}`, check tools list and call correct")

        tool_class = getattr(module_obj, class_name)

        if not tool_class:
            raise ToolError(f"wrong tool name: `{tool_name}`, check tools list and call correct")

        return tool_class(project=self.project)

    def execute(self, tool_name: str, arguments: dict) -> DTOTool:
        try:
            tool_prefix = tool_name.split('__')[0]
            if tool_prefix == ToolPrefixes.SHELL:
                return ToolShell(shell_tools=self._shell_tools, project=self.project).exec(tool_name, arguments.get('args', []))

            tool_class = self._load(tool_name)
            return tool_class.exec(**arguments)
        except ToolError as e:
            return DTOTool(
                tool_name=tool_name,
                result=f"ERROR: {e}",
                error=True
            )
        except TypeError:
            return DTOTool(
                tool_name=tool_name, result="ERROR: wrong command code/arguments, check tools list and call correct",
                error=True
            )