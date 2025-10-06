import os.path

from diff_helper import apply_patch, PatchError
import re
from mcp_helper import tool_call
import json

class CommandInterpreter:
    def __init__(self, mcp_host, project_root):
        self.mcp_host = mcp_host
        self.project_root = project_root

    def _command_read(self, file_path) -> dict:
        content = tool_call(self.mcp_host, 'get_file_text_by_path', {
            'pathInProject': file_path,
            'projectPath': self.project_root
        })

        is_success = False
        if 'error' in content:
            result = content['error']
            result = result.replace(self.project_root, '')
        elif 'status' not in content:
            result = "ERROR: File not exists"
        else:
            is_success = True
            result = content['status']

        response = {'result': result, 'exists': 'status' in content}
        if is_success:
            response['tool_name'] = 'read'
            response['file_path'] = file_path

        return response

    def _command_list(self, path) -> dict:
        absolute_path = os.path.join(self.project_root, path)

        if not os.path.exists(absolute_path):
            return {'result': 'ERROR: Path not exists'}

        result = []
        for _path in os.listdir(str(absolute_path)):
            if os.path.isdir(_path):
                _path += '/'
            result.append(f"- {_path}")

        return {'result': "\n".join(result), 'tool_name': 'list_in_directory'}

    def _command_write(self, file_path, data) -> dict:
        # looking for file exists:
        is_exist = self._command_read(file_path)['exists']
        if is_exist:
            method = 'replace_file_text_by_path'
        else:
            method = 'create_new_file_with_text'

        # trim wrapper
        if type(data) is dict or type(data) is list:
            # workaround for some stupid local LLM
            data = json.dumps(data, ensure_ascii=False, indent=4)

        if type(data) is not str:
            return {'result': "ERROR: file content must be string!"}

        data = data.strip()
        if re.match(r'^```[a-z]+\s', data):
            data = re.sub(r'^```[a-z]+\s', '', data)
        elif data[:3] == '```':
            data = data[3:]

        data = re.sub(r'```$', '', data)

        content = tool_call(self.mcp_host, method, {
            'pathInProject': file_path,
            'text': data.strip(),
            'projectPath': self.project_root
        })

        result = {'result': "True" if 'status' in content else "ERROR: " + content['error']}
        if 'status' in content:
            result['tool_name'] = 'write'
            result['file_path'] = file_path

            if is_exist:
                result['file_edit'] = True
            else:
                result['file_create'] = True

        return result

    def _command_write_diff(self, file_path, str_find, str_replace):
        source_file = self._command_read(file_path)
        if not source_file['exists']:
            return {'result': "ERROR: file not exist"}

        source_code = source_file['result']
        source_code = [_.rstrip() for _ in source_code.split("\n")]

        try:
            patched_file = apply_patch("\n".join(source_code), str_find, str_replace)
        except PatchError as e:
            return {'result': f"ERROR: {e}"}

        content = tool_call(self.mcp_host, 'replace_file_text_by_path', {
            'pathInProject': file_path,
            'text': patched_file.strip(),
            'projectPath': self.project_root
        })

        result = {'result': "True" if 'status' in content else "ERROR: " + content['error']}
        if 'status' in content:
            result['file_edit'] = True
            result['tool_name'] = 'write_diff'
            result['file_path'] = file_path

        return result

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
            else:
                return {"result": "ERROR: wrong tool name, check tools list and call correct"}
        except TypeError:
            return {"result": "ERROR: wrong command code/arguments, check tools list and call correct"}