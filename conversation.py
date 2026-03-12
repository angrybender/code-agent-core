import time
import uuid

from dataclasses import asdict
from markupsafe import escape

from dto.dto_instruction import DTOInstruction
from dto.enums import EventType

_FUNCTION_NAME_TITLES = {
    'list_in_directory': 'list  ',
    'write_file': 'write ',
    'replace_code_in_file': 'patch ',
    'shell_command': 'shell ',
    'read_file': 'read  ',
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
    function_name = message.function
    result_message = message.message
    function_alias = _FUNCTION_NAME_TITLES.get(function_name, function_name)

    if message.type == EventType.AGENT:
        return _agent_call_tpl(message)
    elif message.type == EventType.EXIT:
        output = asdict(message)
        output['hidden'] = True
        return output
    elif message.type == EventType.PENDING:
        message.is_final = False
        message.type = EventType.HTML
        result_message = message.message + "&nbsp;"


    if message.type == EventType.TOOL and not message.is_final:
        suffix = f"<dfn>{message.args[0]}</dfn>" if message.args else ''
        result_message = f'<cite>{function_alias}</cite> {suffix}'

    elif function_name == 'read_file':
        path = message.args[0]
        offset = message.args[1] if len(message.args) >= 2 else None
        limit = message.args[2] if len(message.args) == 3 else None
        if offset is not None and limit is not None:
            suffix = f"[{offset + 1}:{offset + limit + 1}]"
        elif offset is not None:
            suffix = f"[{offset + 1}:]"
        elif limit is not None:
            suffix = f"[:{limit + 1}]"
        else:
            suffix = ''

        result_message = f'<cite>{function_alias}</cite> <dfn>{path}{suffix}</dfn>'

    elif function_name == 'search_file':
        needle = str(escape(message.args[0]))
        ext = message.args[1] if len(message.args) == 2 else ''
        ext = f"*.{ext}" if ext else '*.*'
        result_message = f'<cite>{function_alias}</cite> <dfn>{ext}</dfn> <dfn>{needle}</dfn>'

    elif function_name == 'shell_command':
        command_name = [f"<dfn>{message.args[0]}</dfn>"]

        if len(message.args) > 1:
            command_name += [f"<dfn>{_}</dfn>" for _ in message.args[1]]
        result_message = f'<cite>{function_alias}</cite> {" ".join(command_name)}'

    elif function_name in ['write_file', 'replace_code_in_file']:
        file_link = _file_processing_tpl(message.result)
        result_message = f'<cite>{function_alias}</cite> {file_link}'

    elif message.type == EventType.TOOL:
        suffix = f"<dfn>{message.args[0]}</dfn>" if message.args else ''
        result_message = f'<cite>{function_alias}</cite> {suffix}'

    output = asdict(message)
    output['timestamp'] = time.time()
    output['message'] = result_message

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
    if 'file_edit' in result:
        css_class = 'file_edit'
        a_href = f"#call:jide_open_file//{result['file_path']}//{result['source_file_path']}"
    elif 'file_create' in result:
        css_class = 'file_create'
        a_href = f"#call:jide_open_file//{result['file_path']}"

    return f"<a class='jide_open_file {css_class}' href='{a_href}'>{result['file_name']}</a>"

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