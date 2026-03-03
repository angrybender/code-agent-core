import os
import os.path
import re
import json
import shlex
from commands_helper import execute_terminal_command

from diff_helper import apply_patch, PatchError
from mcp_helper import tool_call
from search_code import SearchCode

SHELL_COMMAND_TIMEOUT = int(os.getenv('SHELL_COMMAND_TIMEOUT', 30))

class ToolsInterpreter:
    def __init__(self, mcp_host, project_root, search_service: SearchCode = None, commands: list = None):
        self.mcp_host = mcp_host
        self.project_root = project_root
        self.search_service = search_service
        self._commands_map = {c['command']: c for c in (commands or [])}

    def _correction_write_arg(self, value) -> str:
        """
        workaround for some stupid local LLM
        :param value:
        :return:
        """
        if type(value) is dict or type(value) is list:
            value = json.dumps(value, ensure_ascii=False, indent=4)

        return value

    def _validate_path(self, path: str) -> bool:
        if path == '.' or path == '':
            return True

        if not path or not isinstance(path, str):
            return False
        if '\x00' in path:
            return False
        normalized = os.path.normpath(path)
        if normalized.startswith('..') or normalized.startswith('/'):
            return False
        real_path = os.path.realpath(os.path.join(self.project_root, normalized))
        project_root_real = os.path.realpath(self.project_root)
        return real_path.startswith(project_root_real + os.sep)

    def _command_read(self, file_path: str, offset: int = 0, limit: int = None) -> dict:
        if not self._validate_path(file_path):
            return {'result': 'ERROR: Invalid path', 'error': True}
        content = tool_call(self.mcp_host, 'get_file_text_by_path', {
            'pathInProject': file_path,
            'projectPath': self.project_root,
        })

        is_success = False
        total_lines = 0
        lines = []
        if 'error' in content:
            result = content['error']
            result = result.replace(self.project_root, '')
        elif 'status' not in content:
            result = "ERROR: File not exists"
        else:
            is_success = True
            full_content = content['status']
            lines = full_content.split('\n')
            total_lines = len(lines)
            lines = lines[offset:]
            if limit is not None:
                lines = lines[:limit]
            result = '\n'.join(lines)

        response = {'result': result, 'exists': 'status' in content}
        if is_success:
            response['tool_name'] = 'read'
            response['file_path'] = file_path
            response['total_lines'] = total_lines
            response['offset'] = offset
            response['returned_lines'] = len(lines)
        else:
            response['error'] = True

        return response

    def _command_list(self, path) -> dict:
        if not self._validate_path(path):
            return {'result': 'ERROR: Invalid path', 'error': True}
        absolute_path = os.path.join(self.project_root, path)

        if not os.path.exists(absolute_path):
            return {'result': 'ERROR: Path not exists'}

        if not os.path.isdir(absolute_path):
            return {'result': 'ERROR: this is a file'}

        result = []
        for _path in os.listdir(str(absolute_path)):
            full_path = os.path.join(absolute_path, _path)
            if os.path.isdir(full_path):
                try:
                    file_count = sum(len(files) for _, _, files in os.walk(full_path, followlinks=False))
                    result.append(f"- {_path}/ (total {file_count} files)")
                except (PermissionError, OSError):
                    result.append(f"- {_path}/ (permission denied)")
            else:
                file_size = os.path.getsize(full_path)
                result.append(f"- {_path} ({file_size} bytes)")

        return {'result': "\n".join(result), 'tool_name': 'list_in_directory'}

    def _command_write(self, file_path, data) -> dict:
        if not self._validate_path(file_path):
            return {'result': 'ERROR: Invalid path', 'error': True}
        # looking for file exists:
        source_file = self._command_read(file_path)
        is_exist = source_file['exists']

        data = self._correction_write_arg(data)
        if type(data) is not str:
            return {'result': "ERROR: file content must be string!"}

        data = data.strip()
        if re.match(r'^```[a-z]+\s', data):
            data = re.sub(r'^```[a-z]+\s', '', data)
        elif data[:3] == '```':
            data = data[3:]

        data = re.sub(r'```$', '', data)

        content = tool_call(self.mcp_host, 'create_new_file', {
            'pathInProject': file_path,
            'text': data.strip(),
            'projectPath': self.project_root,
            'overwrite': True,
        })

        result = {'result': "True" if 'status' in content else "ERROR: " + content['error']}
        if 'status' in content:
            result['tool_name'] = 'write'
            result['file_path'] = os.path.join(self.project_root, file_path)
            result['file_name'] = file_path

            if is_exist:
                result['file_edit'] = True
                result['source_file_content'] = source_file['result']
            else:
                result['file_create'] = True
        else:
            result['error'] = True

        return result

    def _command_write_diff(self, file_path, str_find, str_replace):
        if not self._validate_path(file_path):
            return {'result': 'ERROR: Invalid path', 'error': True}
        source_file = self._command_read(file_path)
        if not source_file['exists']:
            return {'result': "ERROR: file not exist"}

        source_code = source_file['result']
        source_code = [_.rstrip() for _ in source_code.split("\n")]

        str_find = self._correction_write_arg(str_find)
        str_replace = self._correction_write_arg(str_replace)

        try:
            patched_file = apply_patch("\n".join(source_code), str_find, str_replace)
        except PatchError as e:
            return {'result': f"ERROR: {e}", 'error': True}

        content = tool_call(self.mcp_host, 'create_new_file', {
            'pathInProject': file_path,
            'text': patched_file.strip(),
            'projectPath': self.project_root,
            'overwrite': True,
        })

        result = {'result': "True" if 'status' in content else "ERROR: " + content['error']}
        if 'status' in content:
            result['file_edit'] = True
            result['tool_name'] = 'write_diff'
            result['file_path'] = os.path.join(self.project_root, file_path)
            result['file_name'] = file_path
            result['source_file_content'] = source_file['result']
        else:
            result['error'] = True

        return result

    def _search_file(self, needle, extension=None):
        if self.search_service is None:
            return {'error': 'Search service is not available'}
        needle = str(needle).strip()
        if not needle:
            return {'error': 'needle must be a non-empty string', 'tool_name': 'search_file'}
        total_count, results = self.search_service.search(self.project_root, needle, str(extension))
        if not results:
            return {"result": "ERROR: empty search result", "tool_name": "search_file"}

        formatted_result = []
        for result in results:
            formatted_result.append(
                f"file: `{result['file']}`\nline: {result['line_number']}\nfound line: ```{result['found']}```"
            )

        return {"result": "\n\n".join(formatted_result), "tool_name": "search_file", "post_result": f"Found: {total_count} file(s)"}

    def _command_shell(self, command_name: str, args: list = None) -> dict:
        if not command_name or not isinstance(command_name, str):
            return {'result': 'ERROR: command_name must be a non-empty string', 'error': True, 'tool_name': 'shell_command'}

        command_def = self._commands_map.get(command_name)
        if not command_def:
            available = ', '.join(self._commands_map.keys()) or 'none'
            return {'result': f"ERROR: Unknown command '{command_name}'. Available: {available}", 'error': True, 'tool_name': 'shell_command'}
        cmd = command_def['cmd']

        if args and len(args) != len(command_def['args']) or not args and command_def['args']:
            return {'result': f"ERROR: Wrongs '{command_name}' argument list: current: {len(args)}; actual: {len(command_def['args'])}.", 'error': True, 'tool_name': 'shell_command'}

        if args:
            for i, value in enumerate(args, start=1):
                cmd = cmd.replace(f'${i}', str(value))

        raw = execute_terminal_command(cmd=cmd, timeout=SHELL_COMMAND_TIMEOUT, cwd=self.project_root)
        if raw['status'] == 'timeout':
            return {
                'result': f"ERROR: Command timed out after {SHELL_COMMAND_TIMEOUT}s. Partial output: {raw['stdout']}",
                'error': True,
                'tool_name': 'shell_command',
            }
        else:
            output = f"stdout: {raw['stdout']}" if raw['stdout'] else ''
            if raw['stderr']:
                output += f"\n\nstderr: {raw['stderr']}"

            output = output.strip()
            if not output:
                output = raw['status']

            output = f"`$ {cmd}`\n\n```\n{output}\n```"

            return {'result': output, 'tool_name': 'shell_command', 'cmd': cmd, 'status': raw['status']}

    def execute(self, opcode: str, arguments) -> dict:
        try:
            if opcode == 'read_file':
                return self._command_read(*arguments)
            elif opcode == 'list_in_directory':
                return self._command_list(*arguments)
            elif opcode == 'write_file':
                return self._command_write(*arguments)
            elif opcode == 'replace_code_in_file':
                return self._command_write_diff(*arguments)
            elif opcode == 'search_file':
                return self._search_file(*arguments)
            elif opcode == 'shell_command':
                return self._command_shell(*arguments)
            else:
                return {"result": "ERROR: wrong tool name, check tools list and call correct", 'error': True}
        except TypeError:
            return {"result": "ERROR: wrong command code/arguments, check tools list and call correct", 'error': True}