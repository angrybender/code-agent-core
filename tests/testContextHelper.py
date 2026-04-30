import unittest

from context_helper import compact_conversation_remove_redundant


class TestContextHelper(unittest.TestCase):
    def test_write_removes_prior_read_for_same_file(self):
        conversation = [
            {'role': 'system', 'content': 'system1'},
            {'role': 'user', 'content': 'user1'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_1', 'name': 'read_file', 'content': 'content 1'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'write_file', 'arguments': '{"path":"path/file/1.txt","content":"new"}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_2', 'name': 'write_file', 'content': 'ok'},
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])

    def test_write_removes_prior_multi_read_for_same_file(self):
        conversation = [
            {'role': 'system', 'content': 'system1'},
            {'role': 'user', 'content': 'user1'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_multiply_files', 'arguments': '{"root_path":"path/file","file_name":["1.txt","2.txt"]}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_1', 'name': 'read_multiply_files', 'content': 'multi'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'write_file', 'arguments': '{"path":"path/file/1.txt","content":"new"}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_2', 'name': 'write_file', 'content': 'ok'},
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])

    def test_patch_is_not_removed_without_write(self):
        conversation = [
            {'role': 'system', 'content': 'system1'},
            {'role': 'user', 'content': 'user1'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_1', 'name': 'read_file', 'content': 'full'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'replace_code_in_file', 'arguments': '{"path":"path/file/1.txt","str_find":"a","str_replace":"b"}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_2', 'name': 'replace_code_in_file', 'content': 'ok'},
        ]

        self.assertEqual(conversation, compact_conversation_remove_redundant(conversation))

    def test_later_full_read_removes_earlier_full_read_same_path(self):
        conversation = [
            {'role': 'system', 'content': 'system1'},
            {'role': 'user', 'content': 'user1'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"./path/file/1.txt"}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_1', 'name': 'read_file', 'content': 'full1'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_2', 'name': 'read_file', 'content': 'full2'},
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])

    def test_shell_commands_with_different_shell_blocks_are_not_deduplicated(self):
        conversation = [
            {'role': 'system', 'content': 'system1'},
            {'role': 'user', 'content': 'user1'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'shell_command', 'arguments': '{"command_name":"git","shell_block":"git_add_1","args":["a.txt"]}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_1', 'name': 'shell_command', 'content': 'same output'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'shell_command', 'arguments': '{"command_name":"git","shell_block":"git_commit_2","args":["msg"]}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_2', 'name': 'shell_command', 'content': 'same output'},
        ]

        self.assertEqual(conversation, compact_conversation_remove_redundant(conversation))

    def test_shell_commands_with_same_block_and_same_output_are_deduplicated(self):
        conversation = [
            {'role': 'system', 'content': 'system1'},
            {'role': 'user', 'content': 'user1'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'shell_command', 'arguments': '{"command_name":"git","shell_block":"git_status_1","args":[]}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_1', 'name': 'shell_command', 'content': 'same output'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'shell_command', 'arguments': '{"command_name":"git","shell_block":"git_status_1","args":[]}'}
                }]
            },
            {'role': 'tool', 'tool_call_id': 'tool_id_2', 'name': 'shell_command', 'content': 'same output'},
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])


if __name__ == '__main__':
    unittest.main()