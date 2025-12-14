import os
import json
import hashlib
import shutil
import glob

from jinja2 import Environment, BaseLoader

import logging
logger = logging.getLogger('APP')

from dotenv import load_dotenv
load_dotenv()

from utils.llm import llm_query
from command_interpreter import CommandInterpreter
from prompts.analytic_tools import tools as analytic_tools
from prompts.coder_tools import tools as coder_tools

IDE_MCP_HOST=os.getenv('IDE_MCP_HOST')
MAX_ITERATION=int(os.getenv('MAX_ITERATION'))
DEEPTHINKING_AGENTS=os.getenv('DEEPTHINKING_AGENTS', '').split(',')

def _parse_tool_arguments(json_data: str):
    try:
        return json.loads(json_data)
    except json.decoder.JSONDecodeError as e:
        json_data = llm_query(f"fix this JSON: ```{json_data}```\nwrap answer into tag <RESULT>", ['RESULT']).get('RESULT', [''])[0]
        if not json_data:
            raise e

        return json.loads(json_data)


class BaseAgent:
    DEEP_THINK_TAG = 'work_plan'
    STORAGE_PATH = './storage'

    def __init__(self, role: str, system_prompt: str, step_prompt: str, thinking: bool):
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

    def conversation_filter(self, conversation: list[dict]) -> list[dict]:
        return conversation

    def get_tools(self) -> list[dict]:
        return []

    def init(self, instruction: str, manifest: dict, log_file: str):
        self.instruction = instruction
        self.project_description = manifest['description']
        self.project_structure = manifest['files_structure']
        self.interpreter = CommandInterpreter(IDE_MCP_HOST, manifest['base_path'])
        self.log_file = log_file

        self.storage_path = os.path.join(self.STORAGE_PATH, hashlib.sha256(manifest['base_path'].encode()).hexdigest())
        if not os.path.exists(self.storage_path):
            os.mkdir(self.storage_path)

    def run(self):
        assert self.instruction, 'Init() s required'

        yield {
            'message': f"start {self.role}...",
            'result': {},
            'type': "info",
        }

        sub_prompt = self.step_prompt.format(
            project_description=self.project_description,
            project_structure="\n".join([f"- {path}" for path in self.project_structure]),
        )

        self.log("============= INSTRUCTION =============\n" + self.instruction, True)

        conversation = [
            {
                'role': 'system',
                'content': self.system_prompt + "\n" + sub_prompt
            },
            {
                'role': 'user',
                'content': self.instruction
            }
        ]

        agent_step = 1
        max_skip_command = 3
        while True:
            if agent_step > MAX_ITERATION:
                logger.warning("MAX_STEP exceed!")
                yield {
                    'message': "MAX_STEP exceed!",
                    'result': {},
                    'type': "error",
                    'exit': True,
                }
                break

            conversation = self.conversation_filter(conversation)

            # merge multiply assistant messages to once
            if len(conversation) >= 2:
                if conversation[-1]['role'] == 'assistant' and conversation[-2]['role'] == 'assistant':
                    conversation[-2]['content'] += "\n" + conversation[-1]['content']
                    conversation = conversation[:-1]

            yield {'type': 'nope'}
            if self.thinking:
                think_output = llm_query(conversation)
                think_output = think_output.get('_output', '')
                if think_output and think_output.find(f'<{self.DEEP_THINK_TAG}>') > -1:
                    think_output_msg = think_output\
                                            .replace(f'<{self.DEEP_THINK_TAG}>', '')\
                                            .replace(f'</{self.DEEP_THINK_TAG}>', '')
                    yield {
                        'message': think_output_msg,
                        'result': {},
                        'type': "markdown",
                    }

                    conversation.append({
                        'role': 'assistant',
                        'content': think_output
                    })

            output = llm_query(conversation, tools=self.get_tools())
            self.log("============= LLM OUTPUT =============", True)
            self.log('LLM OUTPUT:\n' + output.get('output', ''), True)

            tool_call_description = None
            current_tool_call = None
            tool_calls = output.get('_tool_calls', [])
            if not tool_calls:
                tool_calls = []

            for tool_call in tool_calls:
                tool_call_description = {
                    'function': tool_call.function.name,
                    'id': tool_call.id,
                    'args': list(_parse_tool_arguments(tool_call.function.arguments).values()) if tool_call.function.arguments else []
                }
                current_tool_call = tool_call
                break

            if not current_tool_call and (max_skip_command <= 0 or not output['_output']):
                yield {
                    'message': "Not commands (1), early stop",
                    'result': {},
                    'type': "error",
                    'exit': True,
                }
                break
            elif not current_tool_call and output['_output']:
                max_skip_command -= 1

                yield {
                    'message': output['_output'],
                    'result': {},
                    'type': "markdown",
                    'exit': True,
                }

                conversation.append({
                    'role': 'assistant',
                    'content': output['_output'],
                })

                continue

            self.log(tool_call_description, True)
            conversation.append({
                'role': 'assistant',
                'content': output['_output'],
                'tool_calls': [current_tool_call]
            })

            if tool_call_description['function'] == 'report':
                yield {
                    'message': tool_call_description['args'][0],
                    'result': {},
                    'type': "report",
                    'exit': True,
                }
                break
            else:
                yield {'type': 'nope'}
                result = self.interpreter.execute(tool_call_description['function'], tool_call_description['args'])
                is_success = not result.get('error', False)

                if 'error' in result:
                    del result['error']

                if is_success and 'file_edit' in result:
                    result['source_file_path'] = self.cache_file(result['file_name'], result['source_file_content'])

                if not tool_call_description['args']:
                    tool_call_description['args'] = ['']

                if is_success:
                    yield {
                        'message': f"🔨 {tool_call_description['function']}: {tool_call_description['args'][0]}",
                        'result': result,
                        'type': "info",
                        'exit': False,
                    }

                result_msg = {
                    'role': 'tool',
                    'tool_call_id': current_tool_call.id,
                    'name': current_tool_call.function.name,
                    'content': result['result'],
                }
                self.log("TOOL RESULT:", True)
                self.log(result_msg, True)

                conversation.append(result_msg)

                agent_step += 1

    def log(self, data, to_file=False):
        if type(data) is list or type(data) is dict:
            data = json.dumps(data, ensure_ascii=False, indent=4)

        data = f"[ {self.role} ] {data}"

        if not to_file:
            logger.info(data)
            return

        with open(self.log_file, "a", encoding='utf8') as f:
            f.write(data + "\n\n")

    def cache_file(self, file_name: str, source_file_content: str) -> str:
        source_file_content_path = os.path.join(self.storage_path, hashlib.sha256(file_name.encode()).hexdigest() + '.txt')
        if not os.path.exists(source_file_content_path):
            with open(source_file_content_path, 'w', encoding='utf8') as f:
                f.write(source_file_content)

        return os.path.abspath(source_file_content_path)


class AnalyticAgent(BaseAgent):
    def get_tools(self) -> list[dict]:
        return analytic_tools

class CoderAgent(BaseAgent):
    def get_tools(self) -> list[dict]:
        return coder_tools

    def conversation_filter(self, conversation: list[dict]) -> list[dict]:
        last_tool = ''
        modified_conversation = []
        for m in conversation:
            modified_conversation.append(m)

            if 'tool_calls' not in m:
                continue

            tool = m['tool_calls'][0]
            _hash = tool.function.name + ':' + tool.function.arguments

            if tool.function.name != 'read_file':
                last_tool = _hash
                continue

            if _hash == last_tool:
                modified_conversation.append({
                    'role': 'tool',
                    'tool_call_id': tool.id,
                    'name': tool.function.name,
                    'content': 'File has read above!',
                })

                return modified_conversation
            else:
                last_tool = _hash

        return conversation


class Agent:
    PROMPTS = {
        'ANALYTIC': './prompts/analytic_system.txt',
        'CODER': './prompts/coder_system.txt',
    }

    STEP_PROMPT = './prompts/step.txt'

    @staticmethod
    def setUp():
        for cache_path in glob.glob(os.path.join(BaseAgent.STORAGE_PATH, '*')):
            shutil.rmtree(cache_path)

    @staticmethod
    def fabric(role) -> BaseAgent:
        assert role in Agent.PROMPTS, f'invalid role: {role}'

        thinking = role in DEEPTHINKING_AGENTS
        system_prompt = Agent.PROMPTS[role]
        with open(system_prompt, 'r', encoding='utf8') as f:
            system_prompt = f.read()

            rtemplate = Environment(loader=BaseLoader).from_string(system_prompt)
            system_prompt = rtemplate.render(params={
                'thinking': thinking
            })

        with open(Agent.STEP_PROMPT, 'r', encoding='utf8') as f:
            step_prompt = f.read()


        if role == 'ANALYTIC':
            return AnalyticAgent(role, system_prompt, step_prompt, thinking)
        elif role == 'CODER':
            return CoderAgent(role, system_prompt, step_prompt, False)
