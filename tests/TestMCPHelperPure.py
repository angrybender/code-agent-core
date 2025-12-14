import unittest
import os
import tempfile
import shutil

from utils.mcp_helper import tool_call

class TestMCPHelperPure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix='test_mcp_pure_')
        cls.project_root = cls.test_dir

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def setUp(self):
        for item in os.listdir(self.test_dir):
            item_path = os.path.join(self.test_dir, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

    def test_properly_ent(self):
        self.assertEqual('pure', os.environ.get('AGENT_FILE_TOOLS'))

    def test_tool_call_get_file_text_by_path(self):
        """Test reading via tool_call with get_file_text_by_path."""
        test_file = 'tool_read.txt'
        test_content = 'Content read via tool_call'
        file_path = os.path.join(self.test_dir, test_file)
        
        # Create test file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        # Read via tool_call
        result = tool_call(
            'dummy_host',
            'get_file_text_by_path',
            {
                'projectPath': self.test_dir,
                'pathInProject': test_file
            }
        )
        
        # Verify result
        self.assertIn('status', result)
        self.assertEqual(result['status'], test_content)

    def test_tool_call_create_new_file_pure_mode(self):
        """Test creating file via tool_call in pure mode."""
        test_file = 'tool_write.txt'
        test_content = 'Content written via tool_call'
        
        # Write via tool_call
        result = tool_call(
            'dummy_host',
            'create_new_file',
            {
                'projectPath': self.test_dir,
                'pathInProject': test_file,
                'text': test_content
            }
        )
        
        # Verify result
        self.assertIn('status', result)
        
        # Verify file was created
        file_path = os.path.join(self.test_dir, test_file)
        self.assertTrue(os.path.exists(file_path))
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertEqual(content, test_content)

    def test_tool_call_unknown_tool_raises_exception(self):
        """Test that unknown tool names raise an exception in pure mode."""
        with self.assertRaises(Exception) as context:
            tool_call(
                'dummy_host',
                'unknown_tool',
                {
                    'projectPath': self.test_dir,
                    'pathInProject': 'test.txt'
                }
            )


if __name__ == '__main__':
    unittest.main()