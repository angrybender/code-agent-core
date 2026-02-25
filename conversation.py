import json
import time

def get_message(message: str, role: str, message_type: str=None) -> dict:
    return {
        'role': role,
        'message': message,
        'type': message_type if message_type else 'text',
        'timestamp': time.time()
    }

def get_terminal():
    return get_message('[DONE]', 'assistant', 'end')

def agent_tool_tpl(message: dict) -> dict:
    function_name = message.get('function')

    tool_msg_prefix = "🔨"
    if message['type'] == 'tool' and not message['is_success']:
        tool_msg_prefix += " ❌"

    if function_name == 'read_file':
        path = message['args'][0]
        offset = message['args'][1] if len(message['args']) >= 2 else None
        limit = message['args'][2] if len(message['args']) == 3 else None
        if offset is not None and limit is not None:
            suffix = f"[{offset + 1}:{offset + limit + 1}]"
        elif offset is not None:
            suffix = f"[{offset + 1}:]"
        elif limit is not None:
            suffix = f"[:{limit + 1}]"
        else:
            suffix = ''

        message['message'] = f'{tool_msg_prefix} <cite>read_file</cite> <dfn>{path}{suffix}</dfn>'

    elif function_name == 'search_file':
        needle = message['args'][0].replace('<', '').replace('>', '')
        ext = message['args'][1] if len(message['args']) == 2 else ''
        ext = f"*.{ext}" if ext else '*.*'
        message['message'] = f'{tool_msg_prefix} <cite>search_file</cite> <dfn>{ext}</dfn> <dfn>{needle}</dfn>'

    elif message['type'] == 'tool':
        suffix = f"<dfn>{message['args'][0]}</dfn>" if message['args'] else ''
        message['message'] = f'{tool_msg_prefix} <cite>{function_name}</cite> {suffix}'

    return message

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

def agent_result_tpl(result: dict, message_type: str, message) -> dict:
    tool_name = result.get('tool_name', '')
    if tool_name in ['write', 'write_diff']:
        message_type = 'html'
        file_link = _file_processing_tpl(result)
        message = f"🔨 {tool_name}: {file_link}"

    return {
        'role': 'assistant',
        'message': message,
        'type': message_type,
        'timestamp': time.time()
    }

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
            'timestamp': time.time()
        }

    return None