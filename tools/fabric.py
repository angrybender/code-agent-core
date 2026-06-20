import glob
import re

from pathlib import Path
from importlib import import_module

class ToolsFabric:
    TOOL_PREFIX = 'tool_'

    @staticmethod
    def get_all_tools(filter_module=None) -> list[dict]:
        tools_classes = glob.glob(f'./tools/*/{ToolsFabric.TOOL_PREFIX}*.py')
        class_mapper = []
        for tool_class in tools_classes:
            path = Path(tool_class)
            _, module, tool_name = path.parts

            if filter_module and module != filter_module:
                continue

            tool_name = tool_name.split('.')[0]
            class_name = ''.join(word.capitalize() for word in tool_name.split('_'))
            module_obj = import_module(f"tools.{module}.{tool_name}")
            tool_class = getattr(module_obj, class_name)
            tool_description = tool_class.get_description()
            if tool_description:
                tool_description['name'] = re.sub(f'^{ToolsFabric.TOOL_PREFIX}', '', tool_name)

                class_mapper.append({
                    "type": "function",
                    "function": tool_description
                })

        return class_mapper