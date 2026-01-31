import os.path
import re
import json

from diff_helper import apply_patch, PatchError
from mcp_helper import tool_call
from search_code import SearchCode

class CommandInterpreter:
    def __init__(self, mcp_host, project_root, search_service: SearchCode = None):
        self.mcp_host = mcp_host
        self.project_root = project_root
        if search_service:
            self.search_service = search_service

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

    def _command_read(self, file_path) -> dict:
        if not self._validate_path(file_path):
            return {'result': 'ERROR: Invalid path', 'error': True}
        content = tool_call(self.mcp_host, 'get_file_text_by_path', {
            'pathInProject': file_path,
            'projectPath': self.project_root,
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
                result.append(f"- {_path}/")
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
        results = self.search_service.search(self.project_root, needle, str(extension))
        if not results:
            return {"result": "ERROR: empty search result", "tool_name": "search_file"}

        formatted_result = []
        for result in results:
            formatted_result.append(f"file: `{result['file']}`\nfound line: ```{result['found']}```")

        return {"result": "\n\n".join(formatted_result), "tool_name": "search_file"}

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
            else:
                return {"result": "ERROR: wrong tool name, check tools list and call correct", 'error': True}
        except TypeError:
            return {"result": "ERROR: wrong command code/arguments, check tools list and call correct", 'error': True}