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
        if 'file_edit' in result:
            css_class = 'file_edit'
        elif 'file_create' in result:
            css_class  = 'file_create'

        message = f"🔨 {tool_name}: <a class='jide_open_file {css_class}' href='#call:jide_open_file//{result['file_path']}'>{result['file_path']}</a>",

    return {
        'role': 'assistant',
        'message': message,
        'type': message_type,
        'timestamp': time.time()
    }