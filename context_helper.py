import json
import logging

logger = logging.getLogger('APP')

def compact_conversation_remove_redundant(conversation: list[dict]) -> list[dict]:
    if not conversation:
        return conversation

    last_msg = conversation[-1]
    if 'tool_calls' in last_msg:
        for tc in last_msg['tool_calls']:
            func = tc.get('function', {}).get('name', '')
            if func == 'report':
                return conversation

    last_write_index = {}
    tc_id_to_index = {}
    idx = 0
    for msg in conversation:
        if 'tool_calls' in msg:
            for tc in msg['tool_calls']:
                func = tc.get('function', {}).get('name', '')
                tc_id = tc.get('id')
                if tc_id:
                    tc_id_to_index[tc_id] = idx
                if func in ('write_file', 'replace_code_in_file'):
                    try:
                        args = json.loads(tc.get('function', {}).get('arguments', '{}'))
                        path = args.get('path')
                        if path:
                            last_write_index[path] = idx
                    except (json.JSONDecodeError, TypeError):
                        pass
                idx += 1
            continue
        idx += 1

    ids_to_remove = set()
    for msg in conversation:
        if 'tool_calls' in msg:
            for tc in msg['tool_calls']:
                func = tc.get('function', {}).get('name', '')
                if func == 'read_file':
                    try:
                        args = json.loads(tc.get('function', {}).get('arguments', '{}'))
                        path = args.get('path')
                        tc_id = tc.get('id')
                        if path and tc_id and path in last_write_index:
                            if tc_id_to_index.get(tc_id, 0) < last_write_index[path]:
                                ids_to_remove.add(tc_id)
                    except (json.JSONDecodeError, TypeError):
                        pass

    read_calls_by_path = {}
    has_full_read = {}
    full_read_ids = set()
    for msg in conversation:
        if 'tool_calls' in msg:
            for tc in msg['tool_calls']:
                func = tc.get('function', {}).get('name', '')
                if func == 'read_file':
                    try:
                        args = json.loads(tc.get('function', {}).get('arguments', '{}'))
                        path = args.get('path')
                        tc_id = tc.get('id')
                        if path and tc_id:
                            read_calls_by_path.setdefault(path, []).append(tc_id)
                            if 'offset' not in args and 'limit' not in args:
                                has_full_read[path] = True
                                full_read_ids.add(tc_id)
                    except (json.JSONDecodeError, TypeError):
                        pass

    for path, tc_ids in read_calls_by_path.items():
        if len(tc_ids) > 1 and has_full_read.get(path, False):
            if tc_ids[-1] in full_read_ids:
                for tc_id in tc_ids[:-1]:
                    ids_to_remove.add(tc_id)

    shell_cmd_response = {}
    for msg in conversation:
        if msg.get('role') == 'tool' and msg.get('name') == 'shell_command':
            tc_id = msg.get('tool_call_id')
            if tc_id:
                shell_cmd_response[tc_id] = msg.get('content', '')

    shell_cmd_groups = {}
    for msg in conversation:
        if 'tool_calls' in msg:
            for tc in msg['tool_calls']:
                func = tc.get('function', {}).get('name', '')
                if func == 'shell_command':
                    tc_id = tc.get('id')
                    args_str = tc.get('function', {}).get('arguments', '{}')
                    if tc_id:
                        shell_cmd_groups.setdefault(args_str, []).append(tc_id)

    for args_str, tc_ids in shell_cmd_groups.items():
        if len(tc_ids) > 1:
            responses = [shell_cmd_response.get(tc_id) for tc_id in tc_ids]
            if all(r is not None for r in responses) and len(set(responses)) == 1:
                for tc_id in tc_ids[:-1]:
                    ids_to_remove.add(tc_id)

    if not ids_to_remove:
        return conversation

    result = []
    for msg in conversation:
        if 'tool_calls' in msg:
            dominated = all(tc.get('id') in ids_to_remove for tc in msg['tool_calls'])
            if dominated:
                continue
        if msg.get('role') == 'tool' and msg.get('tool_call_id') in ids_to_remove:
            continue
        result.append(msg)

    return result