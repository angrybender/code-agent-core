import unittest
import os
import re

from tools_interpreter import ToolsInterpreter

class TestToolsInterpreter(unittest.TestCase):
    def test_command_list1(self):
        root_path = os.path.join(os.path.dirname(__file__), '..')
        instance = ToolsInterpreter('', str(root_path))
        result = instance.execute('list_in_directory', {'path': '.'})

        result = result['result'] + '\n'
        self.assertTrue(re.search(r'- tests/ \(total \d+ files\)\n', result), 'dir check - should show file count')
        self.assertTrue(re.search(r'- env\.example \(\d+ bytes, \d+ lines\)\n', result), 'file size check')

    def test_command_list2(self):
        root_path = os.path.join(os.path.dirname(__file__), '..', '_invalid_dir')
        instance = ToolsInterpreter('', str(root_path))
        result = instance.execute('list_in_directory', {'path': '.'})

        self.assertIn('ERROR:', result['result'])