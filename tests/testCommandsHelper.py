import unittest
import os
import shutil
import tempfile

from commands_helper import parse_agent_commands
from tools_interpreter import ToolsInterpreter


class TestParseAgentCommands(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write(self, filename, content):
        path = os.path.join(self.test_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def test_nonexistent_directory(self):
        """Branch: directory does not exist → returns []"""
        result = parse_agent_commands(self.test_dir + '/does_not_exist')
        self.assertEqual([], result)

    def test_empty_directory(self):
        """Branch: directory exists but is empty → returns []"""
        result = parse_agent_commands(self.test_dir)
        self.assertEqual([], result)

    def test_non_md_files_are_skipped(self):
        """Branch: files exist but none end with .md → returns []"""
        self._write('command1.txt', 'some content')
        self._write('command2.py', 'print("hello")')
        self._write('README', 'readme text')
        result = parse_agent_commands(self.test_dir)
        self.assertEqual([], result)

    def test_md_file_without_code_block_is_skipped(self):
        """Branch: .md file has no fenced code blocks → skipped"""
        self._write('deploy.md', 'Just some plain text\nNo code blocks here.')
        result = parse_agent_commands(self.test_dir)
        self.assertEqual([], result)

    def test_single_md_single_code_block(self):
        """Happy path: one .md file with one code block"""
        content = "Run the build script.\n\n```bash\nmake build\n```"
        self._write('build.md', content)
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        self.assertEqual('build', result[0]['command'])
        self.assertEqual('make build', result[0]['cmd'])
        self.assertIn('Run the build script.', result[0]['description'])

    def test_last_code_block_is_used_as_cmd(self):
        """Branch: multiple code blocks → only last one is cmd"""
        content = "Intro.\n\n```sh\necho first\n```\n\nMore text.\n\n```sh\necho second\n```"
        self._write('install.md', content)
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        self.assertEqual('echo second', result[0]['cmd'])

    def test_description_strips_all_code_blocks(self):
        """Branch: description = raw content minus ALL code blocks, stripped"""
        content = (
            "Step 1 description.\n\n"
            "```sh\ncmd1\n```\n\n"
            "Step 2 description.\n\n"
            "```sh\ncmd2\n```"
        )
        self._write('setup.md', content)
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        desc = result[0]['description']
        self.assertIn('Step 1 description.', desc)
        self.assertIn('Step 2 description.', desc)
        self.assertNotIn('cmd1', desc)
        self.assertNotIn('cmd2', desc)
        self.assertNotIn('```', desc)
        self.assertEqual("Step 1 description.\n\n\n\nStep 2 description.", desc)

    def test_cmd_is_stripped(self):
        """Branch: code block body with leading/trailing whitespace → stripped"""
        self._write('test.md', "Desc.\n\n```\n  my command  \n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        self.assertEqual('my command', result[0]['cmd'])

    def test_code_block_with_language_hint(self):
        """Branch: fenced block has language specifier — lang tag not included in cmd"""
        self._write('run.md', "Desc.\n\n```python\nprint('hello')\n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        self.assertEqual("print('hello')", result[0]['cmd'])

    def test_result_dict_has_correct_keys(self):
        """Shape check: each result dict has exactly command, description, cmd keys"""
        self._write('check.md', "Some desc.\n\n```\nsome cmd\n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        self.assertEqual({'command', 'description', 'cmd', 'args'}, set(result[0].keys()))

    def test_description_is_empty_string_when_only_code_block(self):
        """Edge case: file contains only a fenced code block, description becomes empty"""
        self._write('empty_desc.md', "```\nrun me\n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        self.assertEqual('', result[0]['description'])
        self.assertEqual('run me', result[0]['cmd'])

    def test_subdirectory_does_not_crash(self):
        """Branch: subdirectory present → does not crash, not included in results"""
        os.mkdir(os.path.join(self.test_dir, 'subdir'))
        result = parse_agent_commands(self.test_dir)
        self.assertEqual([], result)

    def test_inline_code_fence_is_skipped(self):
        """Edge case: inline fence ```command``` is supported and parsed correctly"""
        self._write('inline.md', "Desc.\n\n```run me```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        self.assertEqual('run me', result[0]['cmd'])
        self.assertEqual('inline', result[0]['command'])

    def test_empty_code_block_body(self):
        """Edge case: code block with whitespace-only body → file is skipped (empty cmd)"""
        self._write('empty_block.md', "Desc.\n\n```\n   \n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual([], result)

    def test_non_sequential_args_raises_exception(self):
        """Command with $1 and $3 but missing $2 must raise ValueError."""
        self._write('cmd.md', "Some description\n\n```\nfoo $1 $3\n```\n")
        with self.assertRaises(ValueError):
            parse_agent_commands(self.test_dir)

    def test_md_skip_no_block_mixed_with_valid(self):
        """Branch: .md without code block is skipped; .md with block is included"""
        self._write('no_block.md', "Plain text, no fenced code.")
        self._write('with_block.md', "Desc.\n\n```\ndo something\n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        self.assertEqual('with_block', result[0]['command'])

class TestShellCommandUnknown(unittest.TestCase):
    """Tests for ToolsInterpreter._command_shell unknown-command error branch."""

    def _make_ti(self, commands=None):
        """Helper: create a ToolsInterpreter with given commands list."""
        return ToolsInterpreter('', '/tmp', commands=commands or [])

    def test_unknown_command_empty_commands_map(self):
        """No commands registered → available reports 'none'"""
        ti = self._make_ti()
        result = ti.execute('shell_command', ['nonexistent'])
        self.assertTrue(result.get('error'))
        self.assertEqual('shell_command', result['tool_name'])
        self.assertIn("Unknown command 'nonexistent'", result['result'])
        self.assertIn('none', result['result'])

    def test_unknown_command_shows_available_names(self):
        """Known commands registered → available lists their names in the error"""
        commands = [
            {'command': 'build', 'cmd': 'make build', 'description': 'Build project', 'args': []},
            {'command': 'lint',  'cmd': 'make lint',  'description': 'Run linter',    'args': []},
        ]
        ti = self._make_ti(commands)
        result = ti.execute('shell_command', ['deploy'])
        self.assertTrue(result.get('error'))
        self.assertEqual('shell_command', result['tool_name'])
        self.assertIn("Unknown command 'deploy'", result['result'])
        self.assertIn('build', result['result'])
        self.assertIn('lint', result['result'])


if __name__ == '__main__':
    unittest.main()