import os
import json
import hashlib
import shutil
import glob
import uuid
import datetime

from jinja2 import Environment, BaseLoader

import logging

from logger_mixin import LoggerMixin
from project import Project

logger = logging.getLogger('APP')

from dotenv import load_dotenv
load_dotenv()

from llm import llm_query_stream, MAX_CONTEXT_WINDOW_SIZE, LLMRequestFormat
from tools_interpreter import ToolsInterpreter
from tools.tools import get_analytic_tools, get_coder_tools, get_reviewer_tools, TOOL_SUMMARIZE, TOOL_REPORT
from dto.dto_instruction import DTOInstruction
from dto.enums import EventType, ToolOperation, ToolPrefixes
from context_helper import compact_conversation_remove_redundant
from agents_logic.tools_mixin import ToolsMixin
from agents_logic.conversation_mixin import ConversationMixin

IDE_MCP_HOST=os.getenv('IDE_MCP_HOST')
MAX_ITERATION=int(os.getenv('MAX_ITERATION'))


class BaseAgent(LoggerMixin, ToolsMixin, ConversationMixin):
    STORAGE_PATH = './storage'

    def __init__(self, role: str, system_prompt: str, step_prompt: str, project: Project, has_shell_commands: bool = True):
        self.interpreter: ToolsInterpreter | None = None
        self.instruction = None
        self.images = []
        self.project_description = None
        self.project_structure = None
        self.current_open_file = None
        self.storage_path = None

        self.system_prompt = system_prompt
        self.step_prompt = step_prompt
        self.project = project
        self.role = role
        self.log_file = role
        self.has_shell_commands = has_shell_commands
        self.artifacts = {
            'files_read': [],
            'files_created': [],
            'files_modified': [],
            'commands_run': [],
        }

    def conversation_filter(self, conversation: list[dict]) -> list[dict]:
        conversation = self.merge_assistant_messages(conversation)

        tools_cnt = len([_ for _ in conversation if 'tool_calls' in _])
        if tools_cnt <= MAX_ITERATION // 2:
            return conversation

        before_len = len(conversation)
        new_conversation = compact_conversation_remove_redundant(conversation)

        if len(new_conversation) < before_len:
            def _create_log(conversation: list[dict]):
                tools_list = [_ for _ in conversation if 'tool_calls' in _]
                for tool in tools_list:
                    tool_call = tool['tool_calls'][0]
                    tool['args'] = list(self.parse_tool_arguments(tool_call['function']['arguments']).values()) if \
                    tool_call['function']['arguments'] else []

                return "; ".join([f'{m['tool_calls'][0]['function']['name']}:{m['args'][0]}' for m in tools_list])

            logger.info(
                "Conv context! Before: " + _create_log(conversation) + " After: " + _create_log(
                    new_conversation)
            )

        return new_conversation

    def get_tools(self) -> list[dict]:
        return []

    def init(self, instruction: str, manifest: dict, log_file: str, images: list = None):
        self.instruction = instruction
        self.images = images if isinstance(images, list) else []
        self.project_description = manifest['description']
        self.project_structure = manifest['files_structure']

        tools = self.project.get_commandlets_tools(self.role)
        self.interpreter = ToolsInterpreter(
            shell_tools={tool['function']['name']: True for tool in tools},
            project=self.project,
        )
        self.log_file = log_file

        self.storage_path = os.path.join(self.STORAGE_PATH, hashlib.sha256(manifest['base_path'].encode()).hexdigest())
        if not os.path.exists(self.storage_path):
            os.mkdir(self.storage_path)

        self.artifacts = {
            'files_read': [],
            'files_created': [],
            'files_modified': [],
            'commands_run': [],
        }

    def _build_artifact_summary(self) -> str:
        """Build a deterministic summary of tracked artifacts"""
        lines = ["## Verified Actions:"]
        files_read = list(dict.fromkeys(self.artifacts['files_read']))  # deduplicate, preserve order
        if files_read:
            lines.append(f"- Files read: {', '.join(files_read)}")
        if self.artifacts['files_created']:
            lines.append(f"- Files created: {', '.join(self.artifacts['files_created'])}")
        if self.artifacts['files_modified']:
            lines.append(f"- Files modified: {', '.join(self.artifacts['files_modified'])}")
        if self.artifacts['commands_run']:
            for cmd in self.artifacts['commands_run']:
                status = cmd.get('status', 'unknown')
                lines.append(f"- Command `{cmd['command']}`: {status}")
        if len(lines) == 1:
            lines.append("- No tool actions recorded yet.")
        return "\n".join(lines)

    def run(self):
        assert self.instruction, 'Init() s required'
        specific_model = os.environ.get(f'MODEL:{self.role}', None)

        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        sub_prompt = self.step_prompt.format(
            project_description=self.project_description,
            project_structure="\n".join([f"- {path}" for path in self.project_structure]),
            current_datetime=current_datetime,
        )

        user_content = self.instruction
        if self.images:
            user_content = [{"type": "text", "text": self.instruction}]
            for img in self.images:
                user_content.append({"type": "image_url", "image_url": {"url": img}})

        conversation = [
            {
                'role': 'system',
                'content': self.system_prompt + "\n" + sub_prompt + f"\nMaximum allowed tools calling: {MAX_ITERATION-1}, dont exceed it!"
            },
            {
                'role': 'user',
                'content': user_content
            }
        ]

        self.log("============= SYSTEM PROMPT =============", True)
        self.log(conversation[0]['content'], True)
        self.log("============= USER PROMPT =============", True)
        self.log(conversation[1]['content'], True)

        agent_step = 0
        _summarize_count = 0  # counts how many times summarize has been triggered
        _context_overflow_summarize = False
        _max_step_workaround = False
        _llm_format_error_workaround = 0
        while True:
            agent_step += 1
            if agent_step > MAX_ITERATION:
                logger.warning("MAX_STEP exceed!")
                yield DTOInstruction(type=EventType.ERROR, message="MAX_STEP exceed!", exit=True)
                break

            conversation = self.conversation_filter(conversation)
            assert conversation, 'Empty conversation'

            yield DTOInstruction(type=EventType.NOPE)

            output = None
            message_id = None
            tools_for_model = self.get_tools()
            force_tool = False
            if _context_overflow_summarize or _max_step_workaround:
                tools_for_model = [TOOL_SUMMARIZE]
                force_tool = True

            if _max_step_workaround or _llm_format_error_workaround > 0:
                tools_for_model = [TOOL_REPORT]
                force_tool = True

            try:
                for chunk in llm_query_stream(conversation, tools=tools_for_model, model_name=specific_model, force_tool=force_tool):
                    message_id = chunk['id']
                    if chunk['type'] == 'final':
                        output = chunk
                        break
                    elif chunk['type'] == 'tool':
                        _tool_call = chunk['tool_calls'][0]
                        yield DTOInstruction(
                            type=EventType.TOOL,
                            is_final=False,
                            function=_tool_call['function']['name'],
                            args=_tool_call['function'].get('arguments_parsed', {}),
                            message_id=chunk['id']
                        )
                    else:
                        yield DTOInstruction(type=EventType.PENDING, message_id=chunk['id'], message=chunk.get('content'), is_final=False)
            except LLMRequestFormat as e:
                if _llm_format_error_workaround <= 3:
                    _llm_format_error_workaround +=1
                    conversation.pop()
                    if _llm_format_error_workaround > 1:
                        conversation.pop() # remove instruction below
                    else:
                        yield DTOInstruction(type=EventType.WARNING, message_id=str(uuid.uuid4()), message=f"LLM error: {e}. Workaround...", is_final=True)

                    conversation.append({
                        'role': 'user',
                        'content': (
                            'IMPORTANT: Create report of the your work. '
                            'Use the `report` tool to provide a comprehensive structured summary of all work done so far. '
                            'Dont continue your work!'
                        )
                    })
                    self.log(f"LLMRequestFormat workaround: {e}")
                    continue
                else:
                    yield DTOInstruction(type=EventType.ERROR, message=str(e), exit=True)
                    return

            _llm_format_error_workaround = 0
            _prompt_tokens = output.get('tokens_usage', {}).get('prompt', 0)
            total_context_size = 0
            if _prompt_tokens > 0:
                total_context_size = _prompt_tokens + output['tokens_usage']['completion']
                yield DTOInstruction(
                    type=EventType.CONTEXT,
                    context_window={"used": total_context_size, "limit": MAX_CONTEXT_WINDOW_SIZE}
                )

            if not output:
                yield DTOInstruction(type=EventType.REPORT, message="", hidden=True, message_id=message_id, metadata={})
                _report = self.create_report(conversation)
                if _report:
                    _report = conversation[-1]['content']
                    logger.info("Empty response. Create report from previous message")
                else:
                    _report = "I've completed task"
                    logger.info("Empty response [agents]")

                yield DTOInstruction(type=EventType.REPORT, message=_report, exit=True, hidden=True, message_id=message_id, metadata=self.artifacts)
                return

            self.log('LLM OUTPUT:\n' + output.get('output', ''), True)

            tool_call_description = None
            current_tool_call = None
            tool_calls = output.get('tool_calls', [])
            if not tool_calls:
                tool_calls = []

            for tool_call in tool_calls:
                _args = self.parse_tool_arguments(tool_call['function']['arguments']) if tool_call['function']['arguments'] else {}
                tool_call_description = {
                    'function': tool_call['function']['name'],
                    'id': tool_call['id'],
                    'args': _args,
                }
                current_tool_call = tool_call
                current_tool_call['function']['arguments'] = json.dumps(_args) # correct json always
                break

            if not current_tool_call and not output['output']:
                _report = self.create_report(conversation)
                if _report:
                    logger.info("Empty response. Create report from previous message (2)")
                else:
                    _report = "Agent has not completed work, empty response"

                yield DTOInstruction(type=EventType.REPORT, message=_report, exit=True, hidden=True, message_id=message_id, metadata=self.artifacts)
                return

            elif not current_tool_call and output['output']:
                yield DTOInstruction(type=EventType.MARKDOWN, message=output['output'], exit=True)

                conversation.append({
                    'role': 'assistant',
                    'content': output['output'],
                })

                continue

            self.log(tool_call_description, True)

            conversation.append({
                'role': 'assistant',
                'content': output['output'] if output['output'] else None,
                'tool_calls': [current_tool_call]
            })

            if tool_call_description['function'] == 'report':
                yield DTOInstruction(
                    type=EventType.REPORT,
                    message=tool_call_description['args'].get('text', '') if tool_call_description['args'] else '',
                    exit=True,
                    message_id=output['id'],
                    metadata=self.artifacts
                )
                break
            elif tool_call_description['function'] == 'summarize':
                    _context_overflow_summarize = False
                    _summarize_count += 1

                    llm_summary = tool_call_description['args'].get('text', '') if tool_call_description['args'] else ''
                    artifact_summary = self._build_artifact_summary()

                    combined_summary = f"{artifact_summary}\n\n## Agent Findings and Progress:\n{llm_summary}"

                    conversation = conversation[:2]

                    # todo `report` tool ?
                    conversation.append({
                        'role': 'assistant',
                        'content': (
                            f"I have summarized my work below (summarization cycle #{_summarize_count}):\n"
                            f"{combined_summary}\n"
                            f"Based on this summary I will continue working."
                        ),
                    })

                    conversation.append({
                        'role': 'system',
                        'content': f"Continue the work of create report!",
                    })

                    self.log(f"SUMMARIZE RESULT:\n{combined_summary}", True)

                    yield DTOInstruction(
                        type=EventType.MARKDOWN,
                        message=tool_call_description['args'].get('text', '') if tool_call_description['args'] else '',
                        message_id=output['id']
                    )

                    continue
            else:
                yield DTOInstruction(type=EventType.NOPE)

                tool_prefix =  tool_call_description['function'].split('__')[0]
                is_pre_output = tool_call_description['function'] == 'search_file' or tool_prefix == ToolPrefixes.SHELL
                response_message_id = output['id'] + ':response'

                if is_pre_output:
                    yield DTOInstruction(
                        type=EventType.TOOL,
                        function=tool_call_description['function'],
                        args=tool_call_description['args'],
                        message_id=output['id']
                    )

                    yield DTOInstruction(
                        type=EventType.PENDING,
                        message_id=response_message_id,
                        is_final=False
                    )

                tool_result = self.interpreter.execute(tool_call_description['function'], tool_call_description['args'])
                is_success = not tool_result.error

                if tool_result.operation == ToolOperation.UPDATE:
                    tool_result.meta['source_file_path'] = self.cache_file(tool_result.file_path)

                if not tool_call_description['args']:
                    tool_call_description['args'] = {}

                if is_success:
                    fn = tool_call_description['function']
                    tool_args = tool_call_description.get('args', {}) if isinstance(tool_call_description.get('args'), dict) else {}
                    if fn == 'read_file':
                        file_path = tool_args.get('path', '')
                        if file_path:
                            self.artifacts['files_read'].append(file_path)
                    elif fn == 'read_multiply_files':
                        root_path = tool_args.get('root_path', '')
                        file_names = tool_args.get('file_name', [])
                        if isinstance(file_names, list):
                            for name in file_names:
                                if name:
                                    file_path = os.path.join(root_path, name) if root_path else name
                                    self.artifacts['files_read'].append(file_path)
                    elif fn == 'write_file':
                        file_path = tool_args.get('path', '')
                        if file_path:
                            if tool_result.operation == ToolOperation.CREATE:
                                self.artifacts['files_created'].append(file_path)
                            elif tool_result.operation == ToolOperation.UPDATE:
                                self.artifacts['files_modified'].append(file_path)
                    elif fn == 'replace_code_in_file':
                        file_path = tool_args.get('path', '')
                        if file_path:
                            self.artifacts['files_modified'].append(file_path)
                    elif fn == 'shell_command':
                        cmd_name = tool_args.get('command_name', '')
                        shell_block = tool_args.get('shell_block', '')
                        command_ref = f'{cmd_name}/{shell_block}' if cmd_name and shell_block else cmd_name or shell_block
                        self.artifacts['commands_run'].append({
                            'command': command_ref,
                            'status': tool_result.meta.get('status', 'unknown')
                        })

                if not is_pre_output:
                    yield DTOInstruction(
                        type=EventType.TOOL,
                        function=tool_call_description['function'],
                        args=tool_call_description['args'],
                        result=tool_result.__dict__,
                        is_success=is_success,
                        message_id=output['id']
                    )

                if is_pre_output:
                    _result = tool_result.output
                    yield DTOInstruction(type=EventType.MARKDOWN, message=_result, message_id=response_message_id, hidden=not is_success)

                result_msg = {
                    'role': 'tool',
                    'tool_call_id': current_tool_call['id'],
                    'name': current_tool_call['function']['name'],
                    'content': tool_result.result
                }
                self.log("TOOL RESULT:", True)
                self.log(result_msg, True)

                conversation.append(result_msg)

            if agent_step == MAX_ITERATION - 1:
                self.log("MAX_ITERATION exceed workaround")
                conversation.append({
                    'role': 'user',
                    'content': (
                        'IMPORTANT: MAX_ITERATION exceed. Create report of the your work'
                        'Use the `report` tool to provide a comprehensive structured summary of all work done so far. '
                        'Dont continue your work - you lead to maximum interation step'
                    )
                })
                _max_step_workaround = True
                continue

            if total_context_size > MAX_CONTEXT_WINDOW_SIZE and not _context_overflow_summarize:
                # TODO: summarization inf loop
                conversation.append({
                    'role': 'user',
                    'content': (
                        'IMPORTANT: The context window is almost full. '
                        'Use the `summarize` tool to provide a comprehensive structured summary of all work done so far. '
                        'Your summary MUST include these sections:\n'
                        '## Files Read: (each file path and key findings)\n'
                        '## Files Created/Modified: (each path and what was done)\n'
                        '## Commands Run: (command name and result)\n'
                        '## Key Findings: (important values, patterns, decisions)\n'
                        '## Current Status: (what is completed)\n'
                        '## What Remains: (what still needs to be done)\n'
                        'Be thorough — target ~3000-4000 characters. Use `summarize` tool now!'
                    )
                })
                _context_overflow_summarize = True
                continue



    def cache_file(self, file_name: str) -> str:
        file_history = self.project.get_file_history(file_name)
        assert len(file_history) > 1, f"For file `{file_name}` where are no history of changes"

        prev_version = file_history[0]['content'] # TODO diff between versions
        source_file_content_path = os.path.join(self.storage_path, hashlib.sha256(file_name.encode()).hexdigest() + '.txt')
        if not os.path.exists(source_file_content_path):
            with open(source_file_content_path, 'w', encoding='utf8') as f:
                f.write(prev_version)

        return os.path.abspath(source_file_content_path)


class AnalyticAgent(BaseAgent):
    def get_tools(self) -> list[dict]:
        if self.role == 'ANALYTIC':
            return get_analytic_tools(self.has_shell_commands) + self.project.get_commandlets_tools(self.role)
        else:
            return get_reviewer_tools(self.has_shell_commands) + self.project.get_commandlets_tools(self.role)

class CoderAgent(BaseAgent):
    def get_tools(self) -> list[dict]:
        return get_coder_tools(self.has_shell_commands) + self.project.get_commandlets_tools(self.role)


class Agent:
    PROMPTS = {
        'ANALYTIC': './prompts/analytic_system.txt',
        'CODER': './prompts/coder_system.txt',
        'REVIEWER': './prompts/reviewer_system.txt',
        'MCP': './prompts/mcp_system.txt',
    }

    STEP_PROMPT = './prompts/step.txt'

    @staticmethod
    def _get_role_agent_commands(role, agent_commands: list = None) -> list:
        if role == 'MCP':
            return []

        filtered_commands = []
        for cmd in agent_commands or []:
            allowed_roles = cmd.get('config', {}).get('role')
            if not allowed_roles or role in allowed_roles:
                filtered_commands.append(cmd)

        return filtered_commands

    @staticmethod
    def setUp():
        for cache_path in glob.glob(os.path.join(BaseAgent.STORAGE_PATH, '*')):
            if os.path.isdir(cache_path):
                shutil.rmtree(cache_path)

    @staticmethod
    def create(role, project: Project, agent_commands: list = None, mcp_commands: list = None) -> BaseAgent:
        assert role in Agent.PROMPTS, f'invalid role: {role}'

        role_agent_commands = Agent._get_role_agent_commands(role, agent_commands)
        has_shell_commands = bool(role_agent_commands and len(role_agent_commands) > 0)
        system_prompt = Agent.PROMPTS[role]
        with open(system_prompt, 'r', encoding='utf8') as f:
            system_prompt = f.read()

            rtemplate = Environment(loader=BaseLoader).from_string(system_prompt)
            system_prompt = rtemplate.render(params={
                'agent_commands': role_agent_commands
            })

        with open(Agent.STEP_PROMPT, 'r', encoding='utf8') as f:
            step_prompt = f.read()

        if role == 'ANALYTIC' or role == 'REVIEWER':
            return AnalyticAgent(role, system_prompt, step_prompt, project=project, has_shell_commands=has_shell_commands)
        elif role == 'CODER':
            return CoderAgent(role, system_prompt, step_prompt, project=project, has_shell_commands=has_shell_commands)
        elif role == 'MCP':
            from mcp_agent import MCPAgent
            return MCPAgent(role, system_prompt, step_prompt, mcp_commands or [], project=project)
        else:
            raise Exception("unknown agent")