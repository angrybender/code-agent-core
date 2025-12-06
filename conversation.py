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
    processed_files_file_path_idx = {}
    for message in messages:
        result = message['message'].get('result', {})
        if (message['type'] == 'files'
            and result.get('tool_name', '') in ['write', 'write_diff']
            and result['file_path'] not in processed_files_file_path_idx
        ):
            processed_files_file_path_idx[ result['file_path'] ] = True
            _html = _file_processing_tpl(result)
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