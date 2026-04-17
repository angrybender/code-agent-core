import unittest
import os
import shutil
import tempfile
from unittest.mock import patch

from commands_helper import parse_agent_commands, execute_terminal_command
from tools_interpreter import ToolsInterpreter
from agents import Agent


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
        self.assertEqual({'command', 'description', 'cmd', 'args', 'config'}, set(result[0].keys()))

    def test_side_effects_true_parsed_from_frontmatter(self):
        self._write('deploy.md', "---\nside_effects: true\n---\nDeploy app.\n\n```bash\n./deploy.sh\n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(True, result[0]['config']['side_effects'])

    def test_frontmatter_excluded_from_description(self):
        self._write('deploy.md', "---\nside_effects: true\n---\nDeploy app.\n\n```bash\n./deploy.sh\n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual('Deploy app.', result[0]['description'])
        self.assertNotIn('side_effects', result[0]['description'])
        self.assertNotIn('---', result[0]['description'])

    def test_frontmatter_preserves_last_code_block_and_arg_parsing(self):
        self._write(
            'deploy.md',
            "---\nside_effects: true\n---\nDeploy app.\n\n$1 - environment name\n\n```bash\necho preview\n```\n\n```bash\n./deploy.sh $1\n```"
        )
        result = parse_agent_commands(self.test_dir)
        self.assertEqual('./deploy.sh $1', result[0]['cmd'])
        self.assertEqual([{'placeholder': '$1', 'description': 'environment name'}], result[0]['args'])
        self.assertIn('Deploy app.', result[0]['description'])
        self.assertNotIn('$1 - environment name', result[0]['description'])

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

    def test_enabled_false_skips_command(self):
        self._write('skip.md', "---\nenabled: false\n---\nDesc.\n\n```\necho skip\n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual([], result)

    def test_enabled_true_includes_command(self):
        self._write('inc.md', "---\nenabled: true\n---\nDesc.\n\n```\necho include\n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        self.assertEqual('echo include', result[0]['cmd'])

    def test_enabled_absent_includes_command(self):
        self._write('default.md', "Desc.\n\n```\necho default\n```")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(1, len(result))
        self.assertEqual('echo default', result[0]['cmd'])

    def test_mcp_commands_returned_for_mcp_type(self):
        """parse_agent_commands with type='mcp' should return commands with mcp: true frontmatter."""
        self._write('test_server.md', "---\nmcp: true\ntype: cli\n---\n# Test MCP Server\n\n```\ndocker run test\n```\n")
        result = parse_agent_commands(self.test_dir, 'mcp')
        self.assertEqual(1, len(result))
        self.assertEqual('test_server', result[0]['command'])

    def test_mcp_commands_excluded_for_shell_type(self):
        """parse_agent_commands with type='shell' should exclude commands with mcp: true frontmatter."""
        self._write('test_server.md', "---\nmcp: true\ntype: cli\n---\n# Test MCP Server\n\n```\ndocker run test\n```\n")
        result = parse_agent_commands(self.test_dir, 'shell')
        self.assertEqual(0, len(result))

    def test_shell_commands_excluded_for_mcp_type(self):
        """parse_agent_commands with type='mcp' should exclude regular shell commands (no mcp: true)."""
        self._write('run_tests.md', "# Run tests\n\n```\npython -m pytest\n```\n")
        result = parse_agent_commands(self.test_dir, 'mcp')
        self.assertEqual(0, len(result))

    def test_default_type_is_shell(self):
        """parse_agent_commands without type_command should default to 'shell' behavior."""
        self._write('test_server.md', "---\nmcp: true\ntype: cli\n---\n# Test MCP Server\n\n```\ndocker run test\n```\n")
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(0, len(result))


class TestShellCommandUnknown(unittest.TestCase):
    """Tests for ToolsInterpreter._command_shell unknown-command error branch."""

    def _make_ti(self, commands=None):
        """Helper: create a ToolsInterpreter with given commands list."""
        return ToolsInterpreter('', '/tmp', commands=commands or [])

    def test_unknown_command_empty_commands_map(self):
        """No commands registered → available reports 'none'"""
        ti = self._make_ti()
        result = ti.execute('shell_command', {'command_name': 'nonexistent'})
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
        result = ti.execute('shell_command', {'command_name': 'deploy'})
        self.assertTrue(result.get('error'))
        self.assertEqual('shell_command', result['tool_name'])
        self.assertIn("Unknown command 'deploy'", result['result'])
        self.assertIn('build', result['result'])
        self.assertIn('lint', result['result'])


class TestAgentCommandFiltering(unittest.TestCase):

    def test_reviewer_filters_side_effect_commands(self):
        commands = [
            {'command': 'build', 'cmd': 'make build', 'description': 'Build', 'args': [], 'config': {'side_effects': False}},
            {'command': 'deploy', 'cmd': './deploy.sh', 'description': 'Deploy', 'args': [], 'config': {'side_effects': True}},
        ]
        self.assertEqual(['build', 'deploy'], [cmd['command'] for cmd in Agent._get_role_agent_commands('CODER', commands)])
        self.assertEqual(['build'], [cmd['command'] for cmd in Agent._get_role_agent_commands('REVIEWER', commands)])
        self.assertEqual(['build'], [cmd['command'] for cmd in Agent._get_role_agent_commands('ANALYTIC', commands)])

    def test_create_uses_filtered_command_list_for_reviewer(self):
        commands = [
            {'command': 'safe', 'cmd': 'echo ok', 'description': 'Safe', 'args': [], 'config': {'side_effects': False}},
            {'command': 'unsafe', 'cmd': 'echo no', 'description': 'Unsafe', 'args': [], 'config': {'side_effects': True}},
        ]
        with patch('agents.AnalyticAgent') as analytic_agent_cls:
            analytic_agent_cls.return_value = object()
            agent = Agent.create('REVIEWER', commands)
            self.assertIsNotNone(agent)
            args = analytic_agent_cls.call_args[0]
            self.assertTrue(args[4])
            self.assertIn('safe', args[1])
            self.assertNotIn('unsafe', args[1])


class TestExecuteTerminalCommand(unittest.TestCase):

    def test_wrong_command_returns_error_status(self):
        result = execute_terminal_command("this_command_does_not_exist_xyz_123", timeout=5)
        self.assertEqual(result['status'], 'error')
        self.assertIn('stdout', result)
        self.assertIn('stderr', result)
        self.assertIn('status', result)

    def test_wrong_command_does_not_raise(self):
        result = execute_terminal_command("this_command_does_not_exist_xyz_123", timeout=5)
        self.assertIsInstance(result, dict)


if __name__ == '__main__':
    unittest.main()