"""Conversation context optimization for LLM token reduction.

Removes redundant tool call/response pairs from conversation history
to reduce context window usage without losing semantically important information.
"""

import json
import os

_WRITE_TOOLS = frozenset({'write_file', 'replace_code_in_file'})
_TOOL_READ_FILE = 'read_file'
_TOOL_READ_MULTIPLY_FILES = 'read_multiply_files'
_TOOL_SHELL_COMMAND = 'shell_command'
_TOOL_REPORT = 'report'


def _normalize_path(path: str) -> str:
    """Normalize a file path string for consistent comparison.
    Handles './' prefix, backslashes, and redundant separators."""
    return os.path.normpath(path).replace("\\", "/")


def _get_tool_name(tool_call: dict) -> str:
    """Extract the function name from a tool call dict."""
    return tool_call.get('function', {}).get('name', '')


def _parse_tool_args(tool_call: dict) -> dict | None:
    """Parse JSON arguments from a tool call. Returns None on failure."""
    try:
        return json.loads(tool_call.get('function', {}).get('arguments', '{}'))
    except (json.JSONDecodeError, TypeError):
        return None


def _last_call_is_report(conversation: list[dict]) -> bool:
    """Check if the last message in the conversation is a 'report' tool call."""
    last_msg = conversation[-1]
    return any(
        _get_tool_name(tool_call) == _TOOL_REPORT
        for tool_call in last_msg.get('tool_calls', [])
    )


def _find_reads_invalidated_by_writes(conversation: list[dict]) -> set[str]:
    """Phase 1: find read_file calls that precede a later write to the same path.

    For each file path, tracks the last write position (write_file or
    replace_code_in_file). Any read_file call that appears before the last
    write to the same path is marked for removal because its content is stale.

    Returns:
        Set of tool_call IDs to remove.
    """
    last_write_position = {}
    tool_call_id_to_position = {}
    # Each tool call within an assistant message gets its own position value,
    # so that we can compare ordering of individual tool calls across messages.
    position = 0
    for msg in conversation:
        if 'tool_calls' in msg:
            for tool_call in msg['tool_calls']:
                tool_name = _get_tool_name(tool_call)
                tool_call_id = tool_call.get('id')
                if tool_call_id:
                    tool_call_id_to_position[tool_call_id] = position
                if tool_name in _WRITE_TOOLS:
                    args = _parse_tool_args(tool_call)
                    if args:
                        path = args.get('path')
                        if path:
                            last_write_position[_normalize_path(path)] = position
                position += 1
            continue
        position += 1

    ids_to_remove: set[str] = set()
    for msg in conversation:
        if 'tool_calls' in msg:
            for tool_call in msg['tool_calls']:
                tool_name = _get_tool_name(tool_call)
                if tool_name == _TOOL_READ_FILE:
                    args = _parse_tool_args(tool_call)
                    if args:
                        path = args.get('path')
                        tool_call_id = tool_call.get('id')
                        norm_path = _normalize_path(path) if path else path
                        if path and tool_call_id and norm_path in last_write_position:
                            if tool_call_id_to_position.get(tool_call_id, 0) < last_write_position[norm_path]:
                                ids_to_remove.add(tool_call_id)
                elif tool_name == _TOOL_READ_MULTIPLY_FILES:
                    args = _parse_tool_args(tool_call)
                    if args:
                        root_path = args.get('root_path', '')
                        file_names = args.get('file_name', [])
                        tool_call_id = tool_call.get('id')
                        if tool_call_id and isinstance(file_names, list):
                            for name in file_names:
                                file_path = os.path.join(root_path, name) if root_path else name
                                norm_file_path = _normalize_path(file_path)
                                if file_path and norm_file_path in last_write_position:
                                    if tool_call_id_to_position.get(tool_call_id, 0) < last_write_position[norm_file_path]:
                                        ids_to_remove.add(tool_call_id)
                                        break

    return ids_to_remove


def _find_duplicate_full_reads(conversation: list[dict]) -> set[str]:
    """Phase 2: deduplicate read_file calls when the last read is a full read.

    For each file path that has a full read (no offset/limit) as the last read,
    removes all prior read_file calls for that same path, keeping only the last one.

    Returns:
        Set of tool_call IDs to remove.
    """
    read_calls_by_path: dict[str, list[str]] = {}
    has_full_read: dict[str, bool] = {}
    full_read_ids: set[str] = set()

    for msg in conversation:
        if 'tool_calls' in msg:
            for tool_call in msg['tool_calls']:
                tool_name = _get_tool_name(tool_call)
                if tool_name == _TOOL_READ_FILE:
                    args = _parse_tool_args(tool_call)
                    if args:
                        path = args.get('path')
                        tool_call_id = tool_call.get('id')
                        norm_path = _normalize_path(path) if path else path
                        if path and tool_call_id:
                            read_calls_by_path.setdefault(norm_path, []).append(tool_call_id)
                            if 'offset' not in args and 'limit' not in args:
                                has_full_read[norm_path] = True
                                full_read_ids.add(tool_call_id)

    ids_to_remove: set[str] = set()
    for path, tool_call_ids in read_calls_by_path.items():
        if len(tool_call_ids) > 1 and has_full_read.get(path, False):
            if tool_call_ids[-1] in full_read_ids:
                # Last read is a full read → remove everything before it (original behavior)
                for tool_call_id in tool_call_ids[:-1]:
                    ids_to_remove.add(tool_call_id)
            else:
                # Full read is NOT the last read — find the last full read index
                last_full_read_index = None
                for i, tool_call_id in enumerate(tool_call_ids):
                    if tool_call_id in full_read_ids:
                        last_full_read_index = i
                if last_full_read_index is not None:
                    reads_after_full = len(tool_call_ids) - 1 - last_full_read_index
                    if reads_after_full >= 2:
                        # Multiple reads after the full read: full read is superseded,
                        # remove the full read and everything before it
                        for tool_call_id in tool_call_ids[:last_full_read_index + 1]:
                            ids_to_remove.add(tool_call_id)
                    # else: single partial after full read → don't compact (UB guard, test 6)

    return ids_to_remove


def _find_duplicate_shell_commands(conversation: list[dict]) -> set[str]:
    """Phase 3: deduplicate identical shell_command calls with identical output.

    For shell_command calls that have the same arguments and produced the same
    output, keeps only the last occurrence and removes all earlier ones.

    Returns:
        Set of tool_call IDs to remove.
    """
    shell_cmd_response: dict[str, str] = {}
    for msg in conversation:
        if msg.get('role') == 'tool' and msg.get('name') == _TOOL_SHELL_COMMAND:
            tool_call_id = msg.get('tool_call_id')
            if tool_call_id:
                shell_cmd_response[tool_call_id] = msg.get('content', '')

    shell_cmd_groups: dict[str, list[str]] = {}
    for msg in conversation:
        if 'tool_calls' in msg:
            for tool_call in msg['tool_calls']:
                tool_name = _get_tool_name(tool_call)
                if tool_name == _TOOL_SHELL_COMMAND:
                    tool_call_id = tool_call.get('id')
                    args_str = tool_call.get('function', {}).get('arguments', '{}')
                    if tool_call_id:
                        shell_cmd_groups.setdefault(args_str, []).append(tool_call_id)

    ids_to_remove: set[str] = set()
    for args_str, tool_call_ids in shell_cmd_groups.items():
        if len(tool_call_ids) > 1:
            responses = [shell_cmd_response.get(tool_call_id) for tool_call_id in tool_call_ids]
            if all(response is not None for response in responses) and len(set(responses)) == 1:
                for tool_call_id in tool_call_ids[:-1]:
                    ids_to_remove.add(tool_call_id)

    return ids_to_remove


def _filter_conversation(conversation: list[dict], ids_to_remove: set[str]) -> list[dict]:
    """Build a filtered conversation list, removing marked tool calls and responses.

    If ALL tool calls in an assistant message are marked for removal, the entire
    assistant message is skipped along with its corresponding tool-role response
    messages.

    Args:
        conversation: Original conversation message list.
        ids_to_remove: Set of tool_call IDs that should be removed.

    Returns:
        A new conversation list with redundant messages removed.
    """
    result = []
    for msg in conversation:
        if 'tool_calls' in msg:
            all_calls_removed = all(
                tool_call.get('id') in ids_to_remove
                for tool_call in msg['tool_calls']
            )
            if all_calls_removed:
                continue
        if msg.get('role') == 'tool' and msg.get('tool_call_id') in ids_to_remove:
            continue
        result.append(msg)
    return result


def compact_conversation_remove_redundant(conversation: list[dict]) -> list[dict]:
    """Remove redundant tool calls from a conversation to shrink context size.

    Applies three optimizations:
    1. Removes read_file calls for paths that were subsequently written
       (write_file / replace_code_in_file), since the read content is stale.
    2. Deduplicates multiple read_file calls for the same path when the last
       call is a full read (no offset/limit) — keeps only the last full read.
    3. Deduplicates identical shell_command calls that produced the same output,
       keeping only the last occurrence.

    Args:
        conversation: List of OpenAI-format message dicts.

    Returns:
        A new (potentially shorter) conversation list, or the original if
        no compaction was possible.
    """
    if not conversation:
        return conversation

    if _last_call_is_report(conversation):
        return conversation

    ids_to_remove: set[str] = set()
    ids_to_remove |= _find_reads_invalidated_by_writes(conversation)
    ids_to_remove |= _find_duplicate_full_reads(conversation)
    ids_to_remove |= _find_duplicate_shell_commands(conversation)

    if not ids_to_remove:
        return conversation

    return _filter_conversation(conversation, ids_to_remove)