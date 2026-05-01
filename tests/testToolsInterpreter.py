import unittest
import os
import re

from project import Project
from tools_interpreter import ToolsInterpreter

class TestToolsInterpreter(unittest.TestCase):
    def test_command_list1(self):
        root_path = os.path.join(os.path.dirname(__file__), '..')
        instance = ToolsInterpreter(project=Project(str(root_path)))
        result = instance.execute('list_in_directory', {'path': '.'})

        result = result.result + '\n'
        self.assertTrue(re.search(r'- tests/ \(total \d+ files\)\n', result), 'dir check - should show file count')
        self.assertTrue(re.search(r'- env\.example \(\d+ bytes, \d+ lines\)\n', result), 'file size check')

    def test_command_list2(self):
        root_path = os.path.join(os.path.dirname(__file__), '..', '_invalid_dir')
        instance = ToolsInterpreter(project=Project(str(root_path)))
        result = instance.execute('list_in_directory', {'path': '.'})

        self.assertIn('ERROR:', result.result)

    def test_read_multiply_files(self):
        root_path = os.path.join(os.path.dirname(__file__), '..')
        instance = ToolsInterpreter(project=Project(str(root_path)))
        result = instance.execute('read_multiply_files', {'root_path': './', 'file_name': ['env.example', 'requirements.txt']})

        self.assertEqual(result.tool_name, 'read_multiply_files')
        self.assertIn('--- file: ./env.example ---', result.result)
        self.assertIn('--- file: ./requirements.txt ---', result.result)

    def test_read_multiply_files_1(self):
        root_path = os.path.join(os.path.dirname(__file__), '..')
        instance = ToolsInterpreter(project=Project(str(root_path)))
        result = instance.execute('read_multiply_files', {'root_path': './tests', 'file_name': ['__init__.py']})

        self.assertEqual(result.tool_name, 'read_multiply_files')
        _path = os.path.join('./tests', '__init__.py')
        self.assertIn(f'--- file: {_path} ---', result.result)

    def test_read_multiply_files_with_invalid_path_1(self):
        root_path = os.path.join(os.path.dirname(__file__), '..')
        instance = ToolsInterpreter(project=Project(str(root_path)))
        result = instance.execute('read_multiply_files', {'root_path': '', 'file_name': ['env.example', 'nonexistent_file_xyz.txt']})

        self.assertEqual(result.tool_name, 'read_multiply_files')
        self.assertIn('--- file: env.example ---', result.result)
        self.assertIn('--- file: nonexistent_file_xyz.txt ---', result.result)

    def test_read_multiply_files_with_invalid_path_2(self):
        root_path = os.path.join(os.path.dirname(__file__), '..')
        instance = ToolsInterpreter(project=Project(str(root_path)))
        result = instance.execute('read_multiply_files', {'root_path': './tests', 'file_name': ['../env.example']})

        self.assertEqual(result.tool_name, 'read_multiply_files')
        self.assertIn('invalid path of /../env.example', result.result)

    def test_read_multiply_files_empty_list(self):
        root_path = os.path.join(os.path.dirname(__file__), '..')
        instance = ToolsInterpreter(project=Project(str(root_path)))
        result = instance.execute('read_multiply_files', {'root_path': '', 'file_name': []})

        self.assertEqual(result.tool_name, 'read_multiply_files')
        self.assertEqual(result.result, '')

    def test_read_multiply_files_single_file(self):
        root_path = os.path.join(os.path.dirname(__file__), '..')
        instance = ToolsInterpreter(project=Project(str(root_path)))
        result = instance.execute('read_multiply_files', {'root_path': '', 'file_name': ['env.example']})

        self.assertEqual(result.tool_name, 'read_multiply_files')
        self.assertIn('--- file: env.example ---', result.result)