import os

from dto.enums import ToolPrefixes
from ide_integration import tool_call
from search_code import SearchCode
from commands_helper import parse_agent_commands, execute_terminal_command


SHELL_COMMAND_TIMEOUT = int(os.getenv('SHELL_COMMAND_TIMEOUT', 30))

class Project:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.files_history = []
        self.search_service = SearchCode()
        shell_cmd_dir = os.getenv('SHELL_COMMAND_DIRECTORY', '.agent-commands')
        full_cmd_dir = os.path.join(self.project_root, shell_cmd_dir)
        self.shell_commands = parse_agent_commands(full_cmd_dir)

    def get_project_root(self) -> str:
        return self.project_root

    def read_file(self, path: str):
        content = tool_call('get_file_text_by_path', {
            'pathInProject': path,
            'projectPath': self.project_root,
        })

        return {
            'content': content.get('status', None),
            'error': content.get('error', None),
        }

    def write_file(self, path: str, content: str):
        content_before = self.read_file(path)
        if content_before['content']:
            content_before = content_before['content']
        else:
            content_before = ''

        abs_path = os.path.join(self.project_root, path)
        version = len(self.files_history)
        self.files_history.append({
            'path': abs_path,
            'content': content_before,
            'version': version + 1
        })

        mcp_result = tool_call('create_new_file', {
            'pathInProject': path,
            'text': content,
            'projectPath': self.project_root,
            'overwrite': True,
        })

        self.files_history.append({
            'path': abs_path,
            'content': content,
            'version': version + 2
        })

        self.search_service.reset()

        return {
            'result': mcp_result.get('status', None),
            'error': mcp_result.get('error', None),
        }

    def get_current_version(self) -> int:
        return len(self.files_history)

    def get_files_history(self, start_version: int, end_version: int) -> list[dict]:
        files_history_result = {}
        if end_version == -1:
            end_version = self.get_current_version()

        for file in self.files_history:
            if start_version <= file['version'] <= end_version:
                if file['path'] not in files_history_result:
                    files_history_result[file['path']] = [file, None]
                else:
                    files_history_result[file['path']][1] = file

        for path, versions in files_history_result.items():
            files_history_result[path] = [_ for _ in versions if _]

        return list(files_history_result.values())

    def get_file_history(self, path: str) -> list[dict]:
        abs_path = os.path.join(self.project_root, path)
        history = []
        for file in self.files_history:
            if file['path'] == abs_path:
                history.append(file)

        return history

    def search_files(self, needle: str, extension: str) -> tuple[int, list[dict]]:
        return self.search_service.search(self.project_root, needle, extension)

    def run_commandlet(self, tool_name: str, args: list = None) -> dict:
        call_cmd = None
        call_arg_cnt = 0
        for commandlet in self.shell_commands:
            for shell_blocks in commandlet.get('shell_blocks', []):
                commandlet_tool_name = f"{ToolPrefixes.SHELL}__{commandlet['command']}_{shell_blocks['name']}"
                if commandlet_tool_name == tool_name:
                    call_cmd = shell_blocks['cmd']
                    call_arg_cnt = len(shell_blocks['args'])
                    break

        if not call_cmd:
            return {
                'error': f'Unknown tool_name.',
                'error_code': 'tool_name',
            }

        if call_arg_cnt != len(args):
            return {
                'error': f"current: {len(args)}; actual: {call_arg_cnt}.",
                'error_code': 'arguments',
            }

        raw = execute_terminal_command(cmd=call_cmd, timeout=SHELL_COMMAND_TIMEOUT, cwd=self.project_root)
        raw['cmd'] = call_cmd

        if raw['status'] == 'timeout':
            raw['error'] = f"Command timed out after {SHELL_COMMAND_TIMEOUT}s. Partial output: {raw['stdout']}"
            raw['error_code'] = 'timeout'

        return raw

    def get_commandlets_tools(self, role_filter: str = None) -> list[dict]:
        commands_tools = []
        for commandlet in self.shell_commands:
            role_access_to = commandlet['config'].get('role', [])
            if role_access_to and role_filter and role_filter not in role_access_to:
                continue

            for shell_blocks in commandlet.get('shell_blocks', []):
                parameters = {
                    "type": "object",
                    "properties": {}
                }
                if shell_blocks['args']:
                    args = []
                    for i, arg in enumerate(shell_blocks['args']):
                        args.append(f"args[{i}] = {arg['description']}  (required)")

                    parameters['required'] = ["args"]
                    parameters['properties'] = {
                        'args': {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": len(shell_blocks['args']),
                            "maxItems": len(shell_blocks['args']),
                            "description": f"Positional arguments for this shell block. Use strict order: {', '.join(args)}"
                        }
                    }

                commands_tools.append({
                    "type": "function",
                    "function": {
                        "name": f"{ToolPrefixes.SHELL}__{commandlet['command']}_{shell_blocks['name']}",
                        "description": shell_blocks['description'],
                        "parameters": parameters
                    }
                })

        return commands_tools
