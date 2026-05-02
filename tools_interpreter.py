import os
import json

from diff_helper import apply_patch, PatchError
from dto.dto_tools import DTOTool
from dto.enums import ToolOperation, ToolPrefixes
from project import Project
from path_helper import ls_la


class ToolError(Exception):
    pass

class ToolsInterpreter:
    def __init__(self, shell_tools: dict = None, project: Project = None):
        self.project_root = project.get_project_root()
        self._shell_tools = shell_tools
        self.project = project

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

    def _command_read(self, path: str, offset: int = 0, limit: int = None) -> DTOTool:
        if not self._validate_path(path):
            raise ToolError('Invalid path')
        content = self.project.read_file(path)

        if content['error']:
            result = content['error']
            result = result.replace(self.project_root, '')
            raise ToolError(result)

        full_content = content['content']
        lines = full_content.split('\n')
        lines = lines[offset:]
        if limit is not None:
            lines = lines[:limit]
        result = '\n'.join(lines)

        return DTOTool(
            result=result,
            operation=ToolOperation.READ,
            tool_name='read',
            file_path=path,
        )

    def _command_read_multiply(self, root_path: str, file_name: list) -> DTOTool:
        results = []
        file_paths = []
        for name in file_name:
            file_path = os.path.join(root_path, name)
            header = f"--- file: {file_path} ---"

            if root_path:
                real_file = os.path.realpath(os.path.join(self.project_root, file_path))
                real_root = os.path.realpath(os.path.join(self.project_root, root_path))
                if not (real_file.startswith(real_root + os.sep) or real_file == real_root):
                    results.append(f"{header}\ninvalid path of /{name}")
                    continue

            file_paths.append(name)
            try:
                single_result = self._command_read(path=file_path)
                results.append(f"{header}\n{single_result.result}")
            except ToolError:
                results.append(f"{header}\ninvalid path of /{name}")

        return DTOTool(
            result="\n\n".join(results),
            tool_name='read_multiply_files',
            file_path="\n".join(file_paths),
            operation=ToolOperation.READ,
        )

    def _command_list(self, path) -> DTOTool:
        if not self._validate_path(path):
            raise ToolError('Invalid path')
        absolute_path = os.path.join(self.project_root, path)

        if not os.path.exists(absolute_path):
            raise ToolError('Path not exists')

        if not os.path.isdir(absolute_path):
            raise ToolError('This is a file, use read file tool')

        result = ls_la(str(absolute_path))
        result = [_['line'] for _ in result]

        return DTOTool(
            result="\n".join(result),
            tool_name='list_in_directory'
        )

    def _command_write(self, path, content) -> DTOTool:
        if not self._validate_path(path):
            raise ToolError('Invalid path')

        # looking for file exists:
        try:
            _ = self._command_read(path).result
            is_exist = True
        except ToolError:
            is_exist = False

        content = self._correction_write_arg(content)
        if type(content) is not str:
            raise ToolError('File content must be string!')

        content = content.strip()
        result = self.project.write_file(path, content)

        if result['error']:
            raise ToolError(result['error'])

        return DTOTool(
            result="True",
            tool_name="write",
            file_path=str(os.path.join(self.project_root, path)),
            operation=ToolOperation.UPDATE if is_exist else ToolOperation.CREATE,
            meta={
                'file_name': path
            }
        )

    def _command_write_diff(self, path, str_find, str_replace) -> DTOTool:
        if not self._validate_path(path):
            raise ToolError('Invalid path')

        try:
            source_file = self._command_read(path)
        except ToolError:
            raise ToolError('File not exist')

        source_code = source_file.result
        source_code = [_.rstrip() for _ in source_code.split("\n")]

        str_find = self._correction_write_arg(str_find)
        str_replace = self._correction_write_arg(str_replace)

        try:
            patched_file = apply_patch("\n".join(source_code), str_find, str_replace)
        except PatchError as e:
            raise ToolError(str(e))

        result = self.project.write_file(path, patched_file.strip())
        if result['error']:
            raise ToolError(result['error'])

        return DTOTool(
            result="True",
            tool_name="write_diff",
            file_path=str(os.path.join(self.project_root, path)),
            operation=ToolOperation.UPDATE,
            meta={
                'file_name': path
            }
        )

    def _search_file(self, needle, extension=None) -> DTOTool:
        needle = str(needle).strip()
        if not needle:
            raise ToolError('Needle must be a non-empty string')

        total_count, results = self.project.search_files(needle, str(extension))
        if not results:
            return DTOTool(
                result="No matches found.",
                tool_name="search_file",
                output="Found: 0 file(s)",
            )

        formatted_result = []
        for result in results:
            formatted_result.append(
                f"file: `{result['file']}`\nline: {result['line_number']}\nfound line: ```{result['found']}```"
            )

        return DTOTool(
            result="\n\n".join(formatted_result),
            tool_name="search_file",
            output=f"Found: {total_count} file(s)",
        )

    def _command_shell(self, tool_name: str, args: list = None) -> DTOTool:
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

    def _get_handlers(self) -> dict:
        return {
            'read_file': self._command_read,
            'read_multiply_files': self._command_read_multiply,
            'list_in_directory': self._command_list,
            'write_file': self._command_write,
            'replace_code_in_file': self._command_write_diff,
            'search_file': self._search_file,
        }

    def execute(self, tool_name: str, arguments: dict) -> DTOTool:
        try:
            tool_prefix = tool_name.split('__')[0]
            if tool_prefix == ToolPrefixes.SHELL:
                return self._command_shell(tool_name, arguments.get('args', []))

            handler = self._get_handlers().get(tool_name)
            if not handler:
                return DTOTool(
                    tool_name=tool_name,
                    result="ERROR: wrong tool name, check tools list and call correct",
                    error=True
                )

            return handler(**arguments)
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