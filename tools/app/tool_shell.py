from dto.dto_tools import DTOTool
from tools.ATool import ATool
from tools.errors import ToolError


class ToolShell(ATool):
    def exec(self, tool_name: str, args: list = None) -> DTOTool:
        if tool_name not in self._shell_tools:
            available = ', '.join(self._shell_tools.keys()) or 'none'
            raise ToolError(f"Unknown command `{tool_name}`. Available: {available}")

        raw = self.project.run_commandlet(tool_name, args)

        if 'error' in raw and raw['error_code'] == 'tool_name':
            available = ', '.join(self._shell_tools.keys()) or 'none'
            raise ToolError(f"Unknown command `{tool_name}`. Available: {available}")

        if 'error' in raw and raw['error_code'] == 'arguments':
            raise ToolError(
                f"Wrongs `{tool_name}` argument list: {raw['error']}."
            )

        if 'error' in raw and raw['status'] == 'timeout':
            raise ToolError(raw['error'])
        else:
            output = f"stdout: {raw['stdout']}" if raw['stdout'] else ''
            if raw['stderr']:
                output += f"\n\nstderr: {raw['stderr']}"

            output = output.strip()
            if not output:
                output = raw['status']

            return DTOTool(
                result=output,
                tool_name='shell_command',
                output=f"`$ {raw['cmd']}`\n\n```\n{output}\n```",
                meta={
                    'status': raw['status'],
                }
            )