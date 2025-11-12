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

def agent_result_tpl(result: dict, message_type: str, message) -> dict:
    tool_name = result.get('tool_name', '')
    if tool_name in ['write', 'write_diff']:
        message_type = 'html'

        css_class = ''
        a_href = '#'
        if 'file_edit' in result:
            css_class = 'file_edit'
            a_href = f"#call:jide_open_file//{result['file_path']}//{result['source_file_path']}"
            result['file_name'] = result['file_name']
        elif 'file_create' in result:
            css_class  = 'file_create'
            a_href = f"#call:jide_open_file//{result['file_path']}"

        message = f"🔨 {tool_name}: <a class='jide_open_file {css_class}' href='{a_href}'>{result['file_name']}</a>",

    return {
        'role': 'assistant',
        'message': message,
        'type': message_type,
        'timestamp': time.time()
    }