import os
import json
import hashlib
import shutil
import glob

from jinja2 import Environment, BaseLoader

import logging

from logger_mixin import LoggerMixin

logger = logging.getLogger('APP')

from dotenv import load_dotenv
load_dotenv()

from llm import llm_query, llm_query_stream
from tools_interpreter import ToolsInterpreter
from tools.tools import ANALYTIC_TOOLS, get_coder_tools, get_reviewer_tools
from search_code import SearchCode
from dto.dto_instruction import DTOInstruction
from dto.enums import EventType
from context_helper import compact_conversation_remove_redundant

IDE_MCP_HOST=os.getenv('IDE_MCP_HOST')
MAX_ITERATION=int(os.getenv('MAX_ITERATION'))
DEEPTHINKING_AGENTS=os.getenv('DEEPTHINKING_AGENTS', '').split(',')
AVOID_EMPTY_RESPONSE = int(os.getenv('AVOID_EMPTY_RESPONSE', 0)) == 1
MAX_CONTEXT_WINDOW_SIZE = int(os.getenv('MAX_CONTEXT_WINDOW_SIZE', 100000))

def _parse_tool_arguments(json_data: str):
    try:
        return json.loads(json_data)
    except json.decoder.JSONDecodeError as e:
        json_data = llm_query(f"fix this JSON: ```{json_data}```\nwrap answer into tag <RESULT>", ['RESULT']).get('RESULT', [''])[0]
        if not json_data:
            raise e

        return json.loads(json_data)

def _merge_assistant_messages(conversation: list[dict]) -> list[dict]:
    # merge multiply assistant messages to once

    merged = True
    while merged:
        merged = False
        if len(conversation) >= 2:
            if conversation[-1]['role'] == 'assistant' and conversation[-2]['role'] == 'assistant':
                conversation[-2]['content'] += "\n" + conversation[-1]['content']
                conversation = conversation[:-1]
                merged = True

    return conversation

def _create_report(conversation: list[dict]):
    report = ""
    last_message = ""
    for message in conversation:
        if message['role'] == 'assistant':
            _content = message['content'].strip()
            if _content:
                last_message = _content

            for tool in message.get('tool_calls', []):
                if tool['function']['name'] == 'report':
                    report += tool['function']['arguments_parsed'].get('text', '')

    report = report.strip()
    if report:
        return report
    else:
        return last_message


class BaseAgent(LoggerMixin):
    DEEP_THINK_TAG = 'work_plan'
    STORAGE_PATH = './storage'

    def __init__(self, role: str, system_prompt: str, step_prompt: str, thinking: bool, has_shell_commands: bool = True):
        self.system_prompt = system_prompt
        self.step_prompt = step_prompt

        self.instruction = None
        self.project_description = None
        self.project_structure = None
        self.current_open_file = None
        self.interpreter = None
        self.role = role
        self.log_file = role
        self.thinking = thinking
        self.storage_path = None
        self.search_service = SearchCode()
        self.has_shell_commands = has_shell_commands
        self.artifacts = {
            'files_read': [],
            'files_created': [],
            'files_modified': [],
            'commands_run': [],
        }

    def conversation_filter(self, conversation: list[dict]) -> list[dict]:
        conversation = _merge_assistant_messages(conversation)
        before_len = len(conversation)
        new_conversation = compact_conversation_remove_redundant(conversation)

        if len(new_conversation) < before_len:
            def _create_log(conversation: list[dict]):
                tools_list = [_ for _ in conversation if 'tool_calls' in _]
                for tool in tools_list:
                    tool_call = tool['tool_calls'][0]
                    tool['args'] = list(_parse_tool_arguments(tool_call['function']['arguments']).values()) if \
                    tool_call['function']['arguments'] else []

                return "; ".join([f'{m['tool_calls'][0]['function']['name']}:{m['args'][0]}' for m in tools_list])

            logger.info(
                "Conv context! Before: " + _create_log(conversation) + " After: " + _create_log(
                    new_conversation)
            )

        return new_conversation

    def get_tools(self) -> list[dict]:
        return []

    def init(self, instruction: str, manifest: dict, log_file: str):
        self.instruction = instruction
        self.project_description = manifest['description']
        self.project_structure = manifest['files_structure']
        self.interpreter = ToolsInterpreter(IDE_MCP_HOST, manifest['base_path'], self.search_service, commands=manifest.get('agent_commands', []))
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

    def run(self):
        assert self.instruction, 'Init() s required'
        specific_model = os.environ.get(f'MODEL:{self.role}', None)
        self.search_service.reset()

        sub_prompt = self.step_prompt.format(
            project_description=self.project_description,
            project_structure="\n".join([f"- {path}" for path in self.project_structure]),
        )

        self.log("============= INSTRUCTION =============\n" + self.instruction, True)

        conversation = [
            {
                'role': 'system',
                'content': self.system_prompt + "\n" + sub_prompt + f"\nMaximum allowed tools calling: {MAX_ITERATION-1}, dont exceed it!"
            },
            {
                'role': 'user',
                'content': self.instruction
            }
        ]

        agent_step = 0
        while True:
            agent_step += 1
            if agent_step > MAX_ITERATION:
                logger.warning("MAX_STEP exceed!")
                yield DTOInstruction(type=EventType.ERROR, message="MAX_STEP exceed!", exit=True)
                break

            conversation = self.conversation_filter(conversation)

            is_empty_workaround = False
            while True:
                yield DTOInstruction(type=EventType.NOPE)

                output = None
                message_id = None
                for chunk in llm_query_stream(conversation, tools=self.get_tools(), model_name=specific_model):
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
                        yield DTOInstruction(type=EventType.PENDING, message_id=chunk['id'], is_final=False)

                if output:
                    break
                else:
                    yield DTOInstruction(type=EventType.REPORT, message="", hidden=True, message_id=message_id, metadata=self.artifacts)

                if not AVOID_EMPTY_RESPONSE:
                    _report = _create_report(conversation)
                    if _report:
                        _report = conversation[-1]['content']
                        logger.info("Empty response. Create report from previous message")
                    else:
                        _report = "I've completed task"
                        logger.info("Empty response [agents]")

                    yield DTOInstruction(type=EventType.REPORT, message=_report, exit=True, hidden=True, message_id=message_id, metadata=self.artifacts)
                    return

                logger.info("Empty response. Force to using tool")

                if not is_empty_workaround:
                    is_empty_workaround = True
                    conversation.append({
                        'role': 'user',
                        'content': 'Dont answer with empty message. If you have finished the work - call `report` tool!'
                    })

            _prompt_tokens = output.get('tokens_usage', {}).get('prompt', 0)
            if _prompt_tokens > 0:
                yield DTOInstruction(
                    type=EventType.CONTEXT,
                    context_window={"used": _prompt_tokens, "limit": MAX_CONTEXT_WINDOW_SIZE}
                )

            self.log('LLM OUTPUT:\n' + output.get('output', ''), True)

            tool_call_description = None
            current_tool_call = None
            tool_calls = output.get('tool_calls', [])
            if not tool_calls:
                tool_calls = []

            for tool_call in tool_calls:
                _args = _parse_tool_arguments(tool_call['function']['arguments']) if tool_call['function']['arguments'] else {}
                tool_call_description = {
                    'function': tool_call['function']['name'],
                    'id': tool_call['id'],
                    'args': _args,
                }
                current_tool_call = tool_call
                current_tool_call['function']['arguments'] = json.dumps(_args) # correct json always
                break

            if not current_tool_call and not output['output']:
                _report = _create_report(conversation)
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
                'content': output['output'],
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
            else:
                yield DTOInstruction(type=EventType.NOPE)

                is_pre_output = tool_call_description['function'] in ['shell_command', 'search_file']
                is_output_resul_of_tool_separate_msg = tool_call_description['function'] in ['shell_command', 'search_file']
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

                result = self.interpreter.execute(tool_call_description['function'], tool_call_description['args'])
                is_success = not result.get('error', False)

                if 'error' in result:
                    del result['error']

                if is_success and 'file_edit' in result:
                    result['source_file_path'] = self.cache_file(result['file_name'], result['source_file_content'])

                if not tool_call_description['args']:
                    tool_call_description['args'] = {}

                if is_success:
                    fn = tool_call_description['function']
                    tool_args = tool_call_description.get('args', {}) if isinstance(tool_call_description.get('args'), dict) else {}
                    if fn == 'read_file':
                        file_path = tool_args.get('path', '')
                        if file_path:
                            self.artifacts['files_read'].append(file_path)
                    elif fn == 'write_file':
                        file_path = tool_args.get('path', '')
                        if file_path:
                            if result.get('file_create'):
                                self.artifacts['files_created'].append(file_path)
                            elif result.get('file_edit'):
                                self.artifacts['files_modified'].append(file_path)
                    elif fn == 'replace_code_in_file':
                        file_path = tool_args.get('path', '')
                        if file_path:
                            self.artifacts['files_modified'].append(file_path)
                    elif fn == 'shell_command':
                        cmd_name = tool_args.get('command_name', '')
                        self.artifacts['commands_run'].append({
                            'command': cmd_name,
                            'status': result.get('status', 'unknown') if isinstance(result, dict) else 'unknown'
                        })

                if not is_pre_output:
                    yield DTOInstruction(
                        type=EventType.TOOL,
                        function=tool_call_description['function'],
                        args=tool_call_description['args'],
                        result=result,
                        is_success=is_success,
                        message_id=output['id']
                    )

                if is_output_resul_of_tool_separate_msg:
                    _result = result.get('post_result', result['result'])
                    yield DTOInstruction(type=EventType.MARKDOWN, message=_result, message_id=response_message_id)

                result_msg = {
                    'role': 'tool',
                    'tool_call_id': current_tool_call['id'],
                    'name': current_tool_call['function']['name'],
                    'content': result['result'],
                }
                self.log("TOOL RESULT:", True)
                self.log(result_msg, True)

                conversation.append(result_msg)

    def cache_file(self, file_name: str, source_file_content: str) -> str:
        source_file_content_path = os.path.join(self.storage_path, hashlib.sha256(file_name.encode()).hexdigest() + '.txt')
        if not os.path.exists(source_file_content_path):
            with open(source_file_content_path, 'w', encoding='utf8') as f:
                f.write(source_file_content)

        return os.path.abspath(source_file_content_path)


class AnalyticAgent(BaseAgent):
    def get_tools(self) -> list[dict]:
        if self.role == 'ANALYTIC':
            return ANALYTIC_TOOLS
        else:
            return get_reviewer_tools(self.has_shell_commands)

class CoderAgent(BaseAgent):
    def get_tools(self) -> list[dict]:
        return get_coder_tools(self.has_shell_commands)


class Agent:
    PROMPTS = {
        'ANALYTIC': './prompts/analytic_system.txt',
        'CODER': './prompts/coder_system.txt',
        'REVIEWER': './prompts/reviewer_system.txt',
    }

    STEP_PROMPT = './prompts/step.txt'

    @staticmethod
    def setUp():
        for cache_path in glob.glob(os.path.join(BaseAgent.STORAGE_PATH, '*')):
            shutil.rmtree(cache_path)

    @staticmethod
    def create(role, agent_commands: list = None) -> BaseAgent:
        assert role in Agent.PROMPTS, f'invalid role: {role}'

        thinking = role in DEEPTHINKING_AGENTS
        has_shell_commands = bool(agent_commands and len(agent_commands) > 0)
        system_prompt = Agent.PROMPTS[role]
        with open(system_prompt, 'r', encoding='utf8') as f:
            system_prompt = f.read()

            rtemplate = Environment(loader=BaseLoader).from_string(system_prompt)
            system_prompt = rtemplate.render(params={
                'thinking': thinking,
                'agent_commands': agent_commands or []
            })

        with open(Agent.STEP_PROMPT, 'r', encoding='utf8') as f:
            step_prompt = f.read()

        if role == 'ANALYTIC' or role == 'REVIEWER':
            return AnalyticAgent(role, system_prompt, step_prompt, thinking, has_shell_commands)
        elif role == 'CODER':
            return CoderAgent(role, system_prompt, step_prompt, False, has_shell_commands)