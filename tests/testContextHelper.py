import unittest

from context_helper import compact_conversation_remove_redundant


class TestContextHelper(unittest.TestCase):
    def test_compact_conversation_remove_redundant_1(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # read file 1
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
            # write file 1
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_3',
                    'type': 'function',
                    'function': {'name': 'write_file', 'arguments': '{"path":"path/file/1.txt","content":"update 1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_3',
                'name': 'write_file',
                'content': 'ok',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        before: system - user - read file1 - read file2 - write file1
        after: system - user - read file2 - write file1
        """
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])
        self.assertEqual(conversation[6], new_conversation[4])
        self.assertEqual(conversation[7], new_conversation[5])

    def test_compact_conversation_remove_redundant_2(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # read file 1
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
            # write file 1
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_3',
                    'type': 'function',
                    'function': {'name': 'write_file', 'arguments': '{"path":"path/file/1.txt","content":"update 1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_3',
                'name': 'write_file',
                'content': 'ok',
            },
            # report
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'type': 'function',
                    'function': {'name': 'report'}
                }]
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        where report - finish work, no need compact
        """
        self.assertEqual(conversation, new_conversation)

    def test_compact_conversation_remove_redundant_3(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # read file 1 10..12 lines
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt","offset":10,"limit":2}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 1',
            },
            # read file 1 14..15 lines
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_11',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt","offset":14,"limit":1}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_11',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 2',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
            # write file 1
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_3',
                    'type': 'function',
                    'function': {'name': 'write_file', 'arguments': '{"path":"path/file/1.txt","content":"update 1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_3',
                'name': 'write_file',
                'content': 'ok',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        before: system - user - read file1;1, read file1:2 - read file2 - write file1
        after: system - user - read file2 - write file1
        """
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[6], new_conversation[2])
        self.assertEqual(conversation[7], new_conversation[3])
        self.assertEqual(conversation[8], new_conversation[4])
        self.assertEqual(conversation[9], new_conversation[5])

    def test_compact_conversation_remove_redundant_4(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # read file 1 partial
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt","offset":10}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt',
            },
            # read file 1 full
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_11',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_11',
                'name': 'read_file',
                'content': 'content of path/file/1.txt',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        before: system - user - read file1 partial - read file1 full - read file2
        after: system - user - read file1 full - read file2
        """
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])
        self.assertEqual(conversation[6], new_conversation[4])
        self.assertEqual(conversation[7], new_conversation[5])

    def test_compact_conversation_remove_redundant_5(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # read file 1 10..12 lines
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt","offset":10,"limit":2}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 1',
            },
            # read file 1 14..15 lines
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_11',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt","offset":14,"limit":1}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_11',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 2',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        dont compact when several partial reading
        """
        self.assertEqual(conversation, new_conversation)

    def test_compact_conversation_remove_redundant_6(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # read file 1 full
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 1',
            },
            # read file 1 partial
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_11',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt","offset":14,"limit":1}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_11',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 2',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        dont compact( UB ): read full file, after read partial
        """
        self.assertEqual(conversation, new_conversation)

    def test_compact_conversation_remove_redundant_7(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # read file 1
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
            # patch file 1
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_3',
                    'type': 'function',
                    'function': {'name': 'replace_code_in_file', 'arguments': '{"path":"path/file/1.txt","content":"update 1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_3',
                'name': 'replace_code_in_file',
                'content': 'ok',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        before: system - user - read file1 - read file2 - patch file1
        after: system - user - read file2 - patch file1
        """
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])
        self.assertEqual(conversation[6], new_conversation[4])
        self.assertEqual(conversation[7], new_conversation[5])

    def test_compact_conversation_remove_redundant_8(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # read file 1 full
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 1',
            },
            # read file 1 partial
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_11',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt","offset":14,"limit":1}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_11',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 2',
            },
            # write file 1
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_3',
                    'type': 'function',
                    'function': {'name': 'write_file', 'arguments': '{"path":"path/file/1.txt","content":"update 1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_3',
                'name': 'write_file',
                'content': 'ok',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_4',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_4',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        before: system - user - read file1 - read file1 partial - read file2 - write file1
        after: system - user - read file2 - write file1
        """
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[6], new_conversation[2])
        self.assertEqual(conversation[7], new_conversation[3])
        self.assertEqual(conversation[8], new_conversation[4])
        self.assertEqual(conversation[9], new_conversation[5])

    def test_compact_conversation_remove_redundant_9(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # patch file 1
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'replace_code_in_file',
                                 'arguments': '{"path":"path/file/1.txt","content":"update 1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'replace_code_in_file',
                'content': 'ok',
            },
            # read file 1
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/1.txt',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_3',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_3',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        dont compact
        """
        self.assertEqual(conversation, new_conversation)

    def test_compact_conversation_remove_redundant_10(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # shell command
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'shell_command', 'arguments': '{"command_name":"command_name_1","args":["1","2"]}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'shell_command',
                'content': 'content of command',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
            # shell command
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_3',
                    'type': 'function',
                    'function': {'name': 'shell_command', 'arguments': '{"command_name":"command_name_1","args":["1","2"]}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_3',
                'name': 'shell_command',
                'content': 'content of command', # same output - compact
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        before: system - user - shell - read file2 - shell
        after: system - user - read file2 - shell
        """
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])
        self.assertEqual(conversation[6], new_conversation[4])
        self.assertEqual(conversation[7], new_conversation[5])

    def test_compact_conversation_remove_redundant_11(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # shell command
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'shell_command', 'arguments': '{"command_name":"command_name_1","args":["1","2"]}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'shell_command',
                'content': 'content of command',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
            # shell command
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_3',
                    'type': 'function',
                    'function': {'name': 'shell_command', 'arguments': '{"command_name":"command_name_1","args":["1","2"]}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_3',
                'name': 'shell_command',
                'content': 'content of command 2', # changed output - dont compact
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        shell return different output: dont compact
        """
        self.assertEqual(conversation, new_conversation)

    def test_compact_conversation_remove_redundant_12(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            # read file 1 full
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 1',
            },
            # read file 1 partial
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_11',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt","offset":14,"limit":1}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_11',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 2',
            },
            # read file 2
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/2.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/2.txt',
            },
            # read file 1 partial
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_3',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt","offset":25,"limit":10}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_3',
                'name': 'read_file',
                'content': 'content of path/file/1.txt 2',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        before: system - user - read file 1 full - read 1 file partial - read file2 - read 1 file partial yet
        after: system - user - read 1 file partial - read file2 - read 1 file partial yet

        if partial read more once after full was read - compact
        """
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])
        self.assertEqual(conversation[6], new_conversation[4])
        self.assertEqual(conversation[7], new_conversation[5])

    def test_path_normalization_phase1_read_with_dot_prefix(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"./path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt',
            },
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'write_file', 'arguments': '{"path":"path/file/1.txt","content":"update 1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'write_file',
                'content': 'ok',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        read uses ./path/file/1.txt, write uses path/file/1.txt - same file, read should be removed
        before: system - user - read file1 (./prefix) - write file1
        after: system - user - write file1
        """
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])

    def test_path_normalization_phase1_write_with_dot_prefix(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt',
            },
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'write_file', 'arguments': '{"path":"./path/file/1.txt","content":"update 1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'write_file',
                'content': 'ok',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        read uses path/file/1.txt, write uses ./path/file/1.txt - same file, read should be removed
        before: system - user - read file1 - write file1 (./prefix)
        after: system - user - write file1
        """
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])

    def test_path_normalization_phase2_duplicate_reads_with_dot_prefix(self):
        conversation = [
            {
                'role': 'system',
                'content': 'system1'
            },
            {
                'role': 'user',
                'content': 'user1'
            },
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_1',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"./path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_1',
                'name': 'read_file',
                'content': 'content of path/file/1.txt',
            },
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [{
                    'id': 'tool_id_2',
                    'type': 'function',
                    'function': {'name': 'read_file', 'arguments': '{"path":"path/file/1.txt"}'}
                }]
            },
            {
                'role': 'tool',
                'tool_call_id': 'tool_id_2',
                'name': 'read_file',
                'content': 'content of path/file/1.txt',
            },
        ]

        new_conversation = compact_conversation_remove_redundant(conversation)

        """
        two full reads of the same file with different path prefixes - first should be removed
        before: system - user - read file1 (./prefix) - read file1
        after: system - user - read file1
        """
        self.assertEqual(conversation[:2], new_conversation[:2])
        self.assertEqual(conversation[4], new_conversation[2])
        self.assertEqual(conversation[5], new_conversation[3])