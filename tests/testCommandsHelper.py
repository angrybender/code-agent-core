import unittest
import os
import shutil
import tempfile
from unittest.mock import patch

from commands_helper import parse_agent_commands, execute_terminal_command
from mcp_integration.mcp_helper import parse_mcp_commands
from project import Project
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
        result = parse_agent_commands(self.test_dir + '/does_not_exist')
        self.assertEqual([], result)

    def test_empty_directory(self):
        result = parse_agent_commands(self.test_dir)
        self.assertEqual([], result)

    def test_non_md_files_are_skipped(self):
        self._write('command1.txt', 'some content')
        self._write('command2.py', 'print("hello")')
        self._write('README', 'readme text')
        result = parse_agent_commands(self.test_dir)
        self.assertEqual([], result)

    def test_md_file_without_separator_is_skipped(self):
        self._write('deploy.md', 'Just some plain text\n```bash\necho hi\n```')
        result = parse_agent_commands(self.test_dir)
        self.assertEqual([], result)

    def test_single_command_with_single_shell_block(self):
        content = "Run the build workflow.\n---\nBuild app\n\n```bash\nmake build\n```"
        self._write('build.md', content)
        result = parse_agent_commands(self.test_dir)

        self.assertEqual(1, len(result))
        self.assertEqual('build', result[0]['command'])
        self.assertEqual('Run the build workflow.', result[0]['description'])
        self.assertEqual(1, len(result[0]['shell_blocks']))
        self.assertEqual('make_build_1', result[0]['shell_blocks'][0]['name'])
        self.assertEqual('Build app', result[0]['shell_blocks'][0]['description'])
        self.assertEqual('make build', result[0]['shell_blocks'][0]['cmd'])
        self.assertEqual([], result[0]['shell_blocks'][0]['args'])

    def test_multi_block_command_parses_all_blocks(self):
        content = (
            'Git helpers\n'
            '---\n'
            'Git diff\n\n'
            '$1 - branch name\n\n'
            '```bash\n'
            'git --no-pager diff $1\n'
            '```\n'
            '---\n'
            'Commit changes\n\n'
            '$1 - commit message\n\n'
            '```bash\n'
            'git commit -m $1\n'
            '```\n'
        )
        self._write('git.md', content)
        result = parse_agent_commands(self.test_dir)

        self.assertEqual(1, len(result))
        self.assertEqual(['git_diff_1', 'git_commit_2'], [block['name'] for block in result[0]['shell_blocks']])
        self.assertEqual('Git diff', result[0]['shell_blocks'][0]['description'])
        self.assertEqual([{'placeholder': '$1', 'description': 'branch name'}], result[0]['shell_blocks'][0]['args'])
        self.assertEqual('Commit changes', result[0]['shell_blocks'][1]['description'])
        self.assertEqual([{'placeholder': '$1', 'description': 'commit message'}], result[0]['shell_blocks'][1]['args'])

    def test_block_name_generation_normalizes_and_truncates(self):
        content = (
            'Desc\n'
            '---\n'
            'Run container\n\n'
            '```bash\n'
            '  docker   run -v D:/x "python:3.12" bash -c "echo ok"\n'
            '```\n'
            '---\n'
            'Second\n\n'
            '```bash\n'
            'VERY-LONG-COMMAND-NAME another-part\n'
            '```\n'
        )
        self._write('docker.md', content)
        result = parse_agent_commands(self.test_dir)

        self.assertEqual('docker_run_1', result[0]['shell_blocks'][0]['name'])
        self.assertEqual('very_long_comman_2', result[0]['shell_blocks'][1]['name'])

    def test_block_args_are_parsed_per_block_only(self):
        content = (
            'Desc\n'
            '---\n'
            'First\n\n'
            '$1 - first arg\n\n'
            '```bash\n'
            'echo $1\n'
            '```\n'
            '---\n'
            'Second\n\n'
            '```bash\n'
            'echo done\n'
            '```\n'
        )
        self._write('cmd.md', content)
        result = parse_agent_commands(self.test_dir)

        self.assertEqual([{'placeholder': '$1', 'description': 'first arg'}], result[0]['shell_blocks'][0]['args'])
        self.assertEqual([], result[0]['shell_blocks'][1]['args'])

    def test_frontmatter_filtered_and_roles_preserved(self):
        self._write(
            'deploy.md',
            '---\nrole: CODER\nenabled: true\n---\nDeploy workflow\n---\nDeploy app\n\n$1 - env\n\n```bash\n./deploy.sh $1\n```'
        )
        result = parse_agent_commands(self.test_dir)

        self.assertEqual('Deploy workflow', result[0]['description'])
        self.assertEqual(['CODER'], result[0]['config']['role'])
        self.assertEqual('deploy_sh_1', result[0]['shell_blocks'][0]['name'])

    def test_enabled_false_skips_command(self):
        self._write('skip.md', '---\nenabled: false\n---\nDesc\n---\n```\necho skip\n```')
        result = parse_agent_commands(self.test_dir)
        self.assertEqual([], result)

    def test_mcp_commands_excluded_for_shell_type(self):
        self._write('test_server.md', '---\nmcp: true\ntype: cli\n---\nMCP helpers\n---\nRun\n\n```\ndocker run test\n```\n')
        result = parse_agent_commands(self.test_dir)
        self.assertEqual(0, len(result))

    def test_non_sequential_args_raises_exception(self):
        self._write('cmd.md', 'Desc\n---\nBroken\n\n```\nfoo $1 $3\n```\n')
        with self.assertRaises(ValueError):
            parse_agent_commands(self.test_dir)

    def test_role_invalid_value_raises(self):
        self._write('bad.md', '---\nrole: INVALID\n---\nDesc\n---\n```\necho bad\n```')
        with self.assertRaises(ValueError):
            parse_agent_commands(self.test_dir)

    def test_result_dict_has_correct_keys(self):
        self._write('check.md', 'Some desc\n---\nBlock desc\n\n```\nsome cmd\n```')
        result = parse_agent_commands(self.test_dir)
        self.assertEqual({'command', 'description', 'shell_blocks', 'config'}, set(result[0].keys()))

    def test_alias_produces_block_name_from_alias(self):
        content = (
            'Run test command\n'
            '---\n'
            'Run test\n\n'
            '```\n'
            '# some name\n'
            'python.exe .\\test_commandlet.py $1 $2\n'
            '```\n'
        )
        self._write('test_commadlet.py.md', content)
        result = parse_agent_commands(self.test_dir)

        self.assertEqual(1, len(result))
        self.assertEqual(1, len(result[0]['shell_blocks']))
        self.assertEqual('some_name_1', result[0]['shell_blocks'][0]['name'])
        self.assertEqual('python.exe .\\test_commandlet.py $1 $2', result[0]['shell_blocks'][0]['cmd'])

    def test_alias_line_removed_from_stored_cmd(self):
        content = (
            'Desc\n'
            '---\n'
            'Run\n\n'
            '```\n'
            '# my alias\n'
            'echo hello world\n'
            '```\n'
        )
        self._write('run.md', content)
        result = parse_agent_commands(self.test_dir)

        self.assertNotIn('# my alias', result[0]['shell_blocks'][0]['cmd'])
        self.assertEqual('echo hello world', result[0]['shell_blocks'][0]['cmd'])

    def test_multiple_blocks_one_alias_one_not(self):
        content = (
            'Multi\n'
            '---\n'
            'First with alias\n\n'
            '```\n'
            '# custom name\n'
            'python.exe script.py\n'
            '```\n'
            '---\n'
            'Second without alias\n\n'
            '```\n'
            'git status\n'
            '```\n'
        )
        self._write('multi.md', content)
        result = parse_agent_commands(self.test_dir)

        self.assertEqual(2, len(result[0]['shell_blocks']))
        self.assertEqual('custom_name_1', result[0]['shell_blocks'][0]['name'])
        self.assertEqual('python.exe script.py', result[0]['shell_blocks'][0]['cmd'])
        self.assertEqual('git_status_2', result[0]['shell_blocks'][1]['name'])
        self.assertEqual('git status', result[0]['shell_blocks'][1]['cmd'])

    def test_alias_only_invalid_chars_falls_back(self):
        content = (
            'Desc\n'
            '---\n'
            'Run\n\n'
            '```\n'
            '# !!!@@@###\n'
            'echo fallback\n'
            '```\n'
        )
        self._write('fallback.md', content)
        result = parse_agent_commands(self.test_dir)

        self.assertEqual('echo_fallback_1', result[0]['shell_blocks'][0]['name'])
        self.assertEqual('echo fallback', result[0]['shell_blocks'][0]['cmd'])

    def test_full_tool_name_format_with_alias(self):
        content = (
            'Desc\n'
            '---\n'
            'Run\n\n'
            '```\n'
            '# deploy prod\n'
            './deploy.sh\n'
            '```\n'
        )
        self._write('release.md', content)
        result = parse_agent_commands(self.test_dir)

        command = result[0]['command']
        block_name = result[0]['shell_blocks'][0]['name']
        tool_name = f'shell__{command}_{block_name}'
        self.assertEqual('shell__release_deploy_prod_1', tool_name)

    def test_alias_without_space_not_treated_as_alias(self):
        content = (
            'Desc\n'
            '---\n'
            'Run\n\n'
            '```\n'
            '#comment\n'
            'echo nospace\n'
            '```\n'
        )
        self._write('nospace.md', content)
        result = parse_agent_commands(self.test_dir)

        self.assertIn('#comment', result[0]['shell_blocks'][0]['cmd'])
        self.assertEqual('comment_echo_1', result[0]['shell_blocks'][0]['name'])

    def test_alias_truncated_to_16_chars(self):
        content = (
            'Desc\n'
            '---\n'
            'Run\n\n'
            '```\n'
            '# this is a very long alias name\n'
            'echo truncate\n'
            '```\n'
        )
        self._write('trunc.md', content)
        result = parse_agent_commands(self.test_dir)

        block_name = result[0]['shell_blocks'][0]['name']
        self.assertTrue(block_name.endswith('_1'))
        name_part = block_name[:-2]
        self.assertLessEqual(len(name_part), 16)


class TestMCPHelper(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write(self, filename, content):
        path = os.path.join(self.test_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def test_nonexistent_directory_returns_empty_list(self):
        result = parse_mcp_commands(self.test_dir + '/does_not_exist')
        self.assertEqual([], result)

    def test_parses_legacy_mcp_command_with_config(self):
        self._write(
            'test_server.md',
            '---\nmcp: true\ntype: cli\nenabled: true\ntimeout: 30\n---\nMCP helpers\n\n```\ndocker run test\n```\n'
        )
        result = parse_mcp_commands(self.test_dir)

        self.assertEqual(1, len(result))
        self.assertEqual('test_server', result[0]['command'])
        self.assertEqual('MCP helpers', result[0]['description'])
        self.assertEqual('docker run test', result[0]['cmd'])
        self.assertEqual('cli', result[0]['config']['type'])
        self.assertEqual(30, result[0]['config']['timeout'])
        self.assertNotIn('mcp', result[0]['config'])
        self.assertNotIn('enabled', result[0]['config'])

    def test_skips_disabled_or_invalid_mcp_files(self):
        self._write('disabled.md', '---\nmcp: true\nenabled: false\n---\nDisabled\n\n```\necho nope\n```\n')
        self._write('missing_block.md', '---\nmcp: true\ntype: cli\n---\nNo command block here')
        self._write('shell_only.md', 'Shell\n---\nRun\n\n```\necho ok\n```\n')

        result = parse_mcp_commands(self.test_dir)
        self.assertEqual([], result)


class TestShellCommandInterpreter(unittest.TestCase):

    def _make_ti(self, commands=None):
        project = Project('/tmp')
        commands = commands or []
        project.shell_commands = commands
        shell_tool_map = {}
        for cmd in commands:
            for block in cmd.get('shell_blocks', []):
                tool_name = f"shell__{cmd['command']}_{block['name']}"
                shell_tool_map[tool_name] = {}
        return ToolsInterpreter(project=project, shell_tools=shell_tool_map)

    def test_unknown_command_empty_commands_map(self):
        ti = self._make_ti()
        result = ti.execute('shell__nonexistent_x_1', {'args': []})
        self.assertTrue(result.error)
        self.assertEqual('shell__nonexistent_x_1', result.tool_name)
        self.assertIn('Unknown command `shell__nonexistent_x_1`', result.result)
        self.assertIn('none', result.result)

    def test_unknown_shell_block_shows_available_names(self):
        commands = [{
            'command': 'build',
            'description': 'Build project',
            'config': {},
            'shell_blocks': [
                {'name': 'make_build_1', 'cmd': 'make build', 'description': 'Build', 'args': []},
                {'name': 'make_test_2', 'cmd': 'make test', 'description': 'Test', 'args': []},
            ]
        }]
        ti = self._make_ti(commands)
        result = ti.execute('shell__build_deploy_1', {'args': []})
        self.assertTrue(result.error)
        self.assertIn('shell__build_deploy_1', result.result)
        self.assertIn('shell__build_make_build_1', result.result)
        self.assertIn('shell__build_make_test_2', result.result)

    @patch('project.execute_terminal_command')
    def test_executes_selected_block_with_args(self, execute_mock):
        execute_mock.return_value = {'stdout': 'ok', 'stderr': '', 'status': 'ok'}
        commands = [{
            'command': 'git',
            'description': 'Git helpers',
            'config': {},
            'shell_blocks': [
                {'name': 'git_add_1', 'cmd': 'git add $1', 'description': 'Add', 'args': [{'placeholder': '$1', 'description': 'file'}]},
                {'name': 'git_status_2', 'cmd': 'git status', 'description': 'Status', 'args': []},
            ]
        }]
        ti = self._make_ti(commands)

        result = ti.execute('shell__git_git_add_1', {'args': ['tests/test.py']})

        execute_mock.assert_called_once()
        self.assertEqual('git add tests/test.py', execute_mock.call_args.kwargs['cmd'])
        self.assertEqual('shell_command', result.tool_name)
        self.assertFalse(result.error)
        self.assertIn('ok', result.result)
        self.assertEqual('ok', result.meta['status'])

    @patch('project.execute_terminal_command')
    def test_executes_selected_block_with_multiple_args(self, execute_mock):
        execute_mock.return_value = {'stdout': 'ok', 'stderr': '', 'status': 'ok'}
        commands = [{
            'command': 'git',
            'description': 'Git helpers',
            'config': {},
            'shell_blocks': [
                {
                    'name': 'git_diff_1',
                    'cmd': 'git diff $1 -- $2',
                    'description': 'Diff file in branch',
                    'args': [
                        {'placeholder': '$1', 'description': 'branch'},
                        {'placeholder': '$2', 'description': 'file'},
                    ]
                },
            ]
        }]
        ti = self._make_ti(commands)

        result = ti.execute('shell__git_git_diff_1', {'args': ['main', 'tests/test.py']})

        execute_mock.assert_called_once()
        self.assertEqual('git diff main -- tests/test.py', execute_mock.call_args.kwargs['cmd'])
        self.assertFalse(result.error)
        self.assertEqual('ok', result.meta['status'])

    def test_argument_validation_is_per_block(self):
        commands = [{
            'command': 'git',
            'description': 'Git helpers',
            'config': {},
            'shell_blocks': [
                {'name': 'git_add_1', 'cmd': 'git add $1', 'description': 'Add', 'args': [{'placeholder': '$1', 'description': 'file'}]},
                {'name': 'git_status_2', 'cmd': 'git status', 'description': 'Status', 'args': []},
            ]
        }]
        ti = self._make_ti(commands)

        wrong = ti.execute('shell__git_git_status_2', {'args': ['extra']})
        self.assertTrue(wrong.error)
        self.assertIn("Wrongs `shell__git_git_status_2` argument list", wrong.result)

        missing = ti.execute('shell__git_git_add_1', {})
        self.assertTrue(missing.error)
        self.assertIn("Wrongs `shell__git_git_add_1` argument list", missing.result)


class TestAgentCommandFiltering(unittest.TestCase):

    def test_role_based_filtering(self):
        commands = [
            {'command': 'all', 'description': 'All', 'shell_blocks': [], 'config': {}},
            {'command': 'coder', 'description': 'Coder', 'shell_blocks': [], 'config': {'role': ['CODER']}},
            {'command': 'review', 'description': 'Review', 'shell_blocks': [], 'config': {'role': ['REVIEWER', 'ANALYTIC']}},
        ]
        self.assertEqual(['all', 'coder'], [cmd['command'] for cmd in Agent._get_role_agent_commands('CODER', commands)])
        self.assertEqual(['all', 'review'], [cmd['command'] for cmd in Agent._get_role_agent_commands('REVIEWER', commands)])
        self.assertEqual(['all', 'review'], [cmd['command'] for cmd in Agent._get_role_agent_commands('ANALYTIC', commands)])
        self.assertEqual([], Agent._get_role_agent_commands('MCP', commands))

    def test_create_uses_filtered_command_list_for_reviewer(self):
        commands = [
            {'command': 'all', 'description': 'All', 'shell_blocks': [{'name': 'echo_all_1', 'description': 'All', 'cmd': 'echo all', 'args': []}], 'config': {}},
            {'command': 'coder_only', 'description': 'Coder', 'shell_blocks': [{'name': 'echo_coder_1', 'description': 'Coder', 'cmd': 'echo coder', 'args': []}], 'config': {'role': ['CODER']}},
            {'command': 'reviewer_only', 'description': 'Reviewer', 'shell_blocks': [{'name': 'echo_reviewer_1', 'description': 'Reviewer', 'cmd': 'echo reviewer', 'args': []}], 'config': {'role': ['REVIEWER']}},
        ]
        project = Project('')
        project.shell_commands = commands

        reviewer_tools = project.get_commandlets_tools('REVIEWER')
        tool_names = [t['function']['name'] for t in reviewer_tools]

        self.assertIn('shell__all_echo_all_1', tool_names)
        self.assertIn('shell__reviewer_only_echo_reviewer_1', tool_names)
        self.assertNotIn('shell__coder_only_echo_coder_1', tool_names)

        coder_tools = project.get_commandlets_tools('CODER')
        coder_tool_names = [t['function']['name'] for t in coder_tools]
        self.assertIn('shell__coder_only_echo_coder_1', coder_tool_names)
        self.assertNotIn('shell__reviewer_only_echo_reviewer_1', coder_tool_names)


class TestExecuteTerminalCommand(unittest.TestCase):

    def test_wrong_command_returns_error_status(self):
        result = execute_terminal_command('this_command_does_not_exist_xyz_123', timeout=5)
        self.assertEqual(result['status'], 'error')
        self.assertIn('stdout', result)
        self.assertIn('stderr', result)
        self.assertIn('status', result)

    def test_wrong_command_does_not_raise(self):
        result = execute_terminal_command('this_command_does_not_exist_xyz_123', timeout=5)
        self.assertIsInstance(result, dict)


if __name__ == '__main__':
    unittest.main()