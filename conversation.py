import time
import uuid

from dataclasses import asdict
from markupsafe import escape

from dto.dto_instruction import DTOInstruction
from dto.enums import EventType, ToolOperation, ToolPrefixes

_FUNCTION_NAME_TITLES = {
    'list_in_directory': 'list  ',
    'write_file': 'write ',
    'replace_code_in_file': 'patch ',
    'read_file': 'read  ',
    'attach_image': 'attach',
    'read_multiply_files': 'read  ',
    'search_file': 'search',
    'select_mcp': 'select',
}

_FUNCTION_ARG_PRINT = {
    'list_in_directory': 'path',
    'write_file': 'path',
    'replace_code_in_file': 'path',
    'read_file': 'path',
    'attach_image': 'path',
    'read_multiply_files': 'root_path',
    'select_mcp': 'server_name',
}

def get_message(message: str, role: str, message_type: str=None) -> dict:
    return {
        'role': role,
        'message': message,
        'type': message_type if message_type else 'text',
        'timestamp': time.time()
    }

def get_terminal():
    return get_message('[DONE]', 'assistant', 'end')

def agent_tool_tpl(message: DTOInstruction) -> dict:
    if message.type == EventType.CONTEXT:
        output = asdict(message)
        output['timestamp'] = time.time()
        return output

    function_name = message.function
    result_message = message.message
    function_alias = _FUNCTION_NAME_TITLES.get(function_name, function_name)
    message_if_final = message.is_final

    if message.type == EventType.AGENT:
        return _agent_call_tpl(message)
    elif message.type == EventType.EXIT:
        output = asdict(message)
        output['hidden'] = True
        output['message_if_final'] = message_if_final
        return output
    elif message.type == EventType.PENDING:
        message.is_final = False
        message.type = EventType.HTML
        result_message = message.message if message.message else ''
        if result_message and '<' not in result_message:
            result_message = f"<span class='pending-title'>{result_message}</span>"

        result_message += "&nbsp;"


    if function_name == 'read_file' and message.is_final:
        path = message.args['path']
        offset = message.args.get('offset')
        limit = message.args.get('limit')
        if offset is not None and limit is not None:
            suffix = f"[{offset + 1}:{offset + limit + 1}]"
        elif offset is not None:
            suffix = f"[{offset + 1}:]"
        elif limit is not None:
            suffix = f"[:{limit + 1}]"
        else:
            suffix = ''

        result_message = f'<cite>{function_alias}</cite> <dfn>{path}{suffix}</dfn>'

    elif function_name == 'read_multiply_files' and message.is_final:
        root_path = message.args.get('root_path')
        paths = ""
        if root_path:
            paths = f"<dfn>{root_path.strip('/\\')}/*</dfn> "

        paths += " ".join([f"<dfn>{_}</dfn>" for _ in message.args.get('file_name', [])])
        result_message = f'<cite>{function_alias}</cite> {paths}'

    elif function_name == 'search_file' and message.is_final:
        needle = str(escape(message.args['needle']))
        ext = message.args.get('extension', '')
        ext = f"*.{ext}" if ext else '*.*'
        result_message = f'<cite>{function_alias}</cite> <dfn>{ext}</dfn> <dfn>{needle}</dfn>'

    elif function_name and function_name[:len(ToolPrefixes.SHELL) + 2] == f'{ToolPrefixes.SHELL}__' and message.is_final:
        command_name = [f"<dfn>{function_name[len(ToolPrefixes.SHELL) + 2:]}</dfn>"]

        if 'args' in message.args:
            command_name += [f"<dfn>{_}</dfn>" for _ in message.args['args']]
        result_message = f'<cite>shell </cite> {" ".join(command_name)}'

    elif function_name in ['write_file', 'replace_code_in_file'] and message.is_final:
        file_link = _file_processing_tpl(message.result)
        result_message = f'<cite>{function_alias}</cite> {file_link}'

    elif function_name in ['report', 'summarize'] and not message.is_final:
        result_message = message.args.get('text', '')
        if result_message:
            message = DTOInstruction(type=EventType.MARKDOWN, message_id=message.message_id)
        else:
            result_message = f'<cite>{function_alias}</cite>'

        message_if_final = True

    elif message.type == EventType.TOOL and function_name[:4] == 'mcp:' and message.is_final:
        result_message = f'<cite>{function_alias}</cite>'
        _info = ''
        if message.args:
            for arg_name, arg_value in message.args.items():
                _info += f'<dt>{arg_name}</dt><dd><pre>{arg_value}</pre></dd>'

            result_message += f'<dl>{_info}</dl>'

    elif message.type == EventType.TOOL:
        if function_name == 'shell_command':
            shell_ref = ''
            if message.args.get('command_name') and message.args.get('shell_block'):
                shell_ref = f"<dfn>{message.args['command_name']}/{message.args['shell_block']}</dfn>"
            shell_args = " ".join([f"<dfn>{_}</dfn>" for _ in message.args.get('args', [])])
            suffix = " ".join([part for part in [shell_ref, shell_args] if part])
        else:
            _arg_name = _FUNCTION_ARG_PRINT.get(str(function_name))
            if _arg_name and _arg_name in message.args:
                _arg = message.args[_arg_name]
                if isinstance(_arg, str): _arg = [_arg]
                suffix = " ".join([f"<dfn>{_}</dfn>" for _ in _arg])
            else:
                suffix = ''

        result_message = f'<cite>{function_alias}</cite> {suffix}'

    output = asdict(message)
    output['timestamp'] = time.time()
    output['message'] = result_message
    output['is_final'] = message_if_final

    if not output['message_id']:
        output['message_id'] = str(uuid.uuid4())

    return output

def _agent_call_tpl(message: DTOInstruction) -> dict:
    agent_name = message.function
    result_message = f'<cite>{agent_name}</cite>'

    output = asdict(message)
    output['timestamp'] = time.time()
    output['message'] = result_message

    if not output['message_id']:
        output['message_id'] = str(uuid.uuid4())

    return output

def _file_processing_tpl(result: dict) -> str:
    css_class = ''
    a_href = '#'
    if result['operation'] == ToolOperation.UPDATE:
        css_class = 'file_edit'
        a_href = f"#call:jide_open_file//{result['file_path']}//{result['meta']['source_file_path']}"
    elif result['operation'] == ToolOperation.CREATE:
        css_class = 'file_create'
        a_href = f"#call:jide_open_file//{result['file_path']}"

    if 'file_name' in result['meta']:
        return f"<a class='jide_open_file {css_class}' href='{a_href}'>{result['meta']['file_name']}</a>"
    else:
        return '-'

def agent_result_of_all_active_tpl(messages: list[dict]) -> dict|None:
    processed_files = []
    for message in messages:
        result = message['message'].get('result', {})
        if message['type'] == 'files' and result.get('tool_name', '') in ['write', 'write_diff']:
            _html = _file_processing_tpl(result)
            if _html not in processed_files:
                processed_files.append(_html)

    if processed_files:
        message = "<p>📋 Processed files:</p> <ul>" + " ".join([f"<li>{link}</li>" for link in processed_files]) + "</ul>"

        return {
            'role': 'assistant',
            'message': message,
            'type': 'html',
            'timestamp': time.time(),
            'message_id': str(uuid.uuid4())
        }

    return None