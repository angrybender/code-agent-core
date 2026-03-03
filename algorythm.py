import json
import os
import glob
import datetime

from dto.dto_instruction import DTOInstruction
from dto.enums import EventType
from log_helper import pretty_print_as_json
from mcp_helper import tool_call
from llm import llm_query_stream
from path_helper import get_relative_path
from tools_interpreter import ToolsInterpreter
from agents import Agent
from tools.tools import SUPERVISOR_TOOLS

from commands_helper import parse_agent_commands
from dotenv import load_dotenv

load_dotenv()

IDE_MCP_HOST=os.getenv('IDE_MCP_HOST')
MAX_ITERATION=os.getenv('MAX_ITERATION')
AVOID_EMPTY_RESPONSE = int(os.getenv('AVOID_EMPTY_RESPONSE', 0)) == 1

import logging
logger = logging.getLogger('APP')
logging.basicConfig(level=logging.INFO)


class Copilot:
    PROJECT_DESCRIPTION = "./AGENTS.md"
    MAX_STEP = int(MAX_ITERATION)
    LOG_FILE = './conversations_log/log.log'

    def __init__(self, instruction: str, session: dict):
        self.output = []
        self.last_step = None
        self.last_tool = {}
        self.manifest = {}
        self.session = session
        self.instruction = instruction

        self.interpreter = None

        self.system_prompt = ''
        self.prompt = ''
        self.executed_commands = []
        self.agent_step = 0

        self.command_state = []

    def get_manifest(self, project_base_path: str):
        content = tool_call(IDE_MCP_HOST, 'get_file_text_by_path', {
            'pathInProject': self.PROJECT_DESCRIPTION,
            'projectPath': project_base_path
        })

        if 'error' in content or 'status' not in content:
            return ''
        else:
            return content['status']

    def _init(self):
        assert 'project_base_path' in self.session, 'Session not contains `project_base_path`'

        if not self.system_prompt:
            self.system_prompt = open('./prompts/supervisor_system.txt', 'r', encoding='utf8').read()

        if not self.prompt:
            self.prompt = open('./prompts/step.txt', 'r', encoding='utf8').read()

        assert self.instruction, 'Empty instruction'

        self.manifest = {
            'base_path': self.session['project_base_path'],
            'description': self.get_manifest(self.session['project_base_path']).strip(),
            'files_structure': self._read_project_structure(self.session['project_base_path']),
        }

        shell_cmd_dir = os.getenv('SHELL_COMMAND_DIRECTORY', '.agent-commands')
        full_cmd_dir = os.path.join(self.session['project_base_path'], shell_cmd_dir)
        self.agent_commands = parse_agent_commands(full_cmd_dir)
        self.manifest['agent_commands'] = self.agent_commands

        self.output = []

        self.executed_commands = []
        self.command_state = []
        self.agent_step = 1
        self.interpreter = ToolsInterpreter(IDE_MCP_HOST, self.session['project_base_path'])

    def _read_project_structure(self, base_path) -> list:
        result = []
        for dir_object in glob.glob(base_path + "/*"):
            is_dir = os.path.isdir(dir_object)

            dir_object = get_relative_path(base_path, dir_object)

            if is_dir:
                dir_object = dir_object + "/"

            result.append(dir_object)
        return result

    def run(self):
        specific_model = os.environ.get('MODEL:SUPERVISOR', None)

        self._init()
        Agent.setUp()

        if self.agent_commands:
            names = "\n".join(f"- **{c['command']}** `{c['cmd']}`" for c in self.agent_commands)
            yield DTOInstruction(type=EventType.MARKDOWN, message=f"Available shell commands:\n{names}")

        with open(self.LOG_FILE, "w", encoding='utf8') as f:
            f.write(str(datetime.datetime.now()) + "\n\n")

        self.log(f"RUN. Messages: `{self.instruction}`", False)

        sub_prompt = self.prompt.format(
            project_description=self.manifest['description'],
            project_structure="\n".join([f"- {path}" for path in self.manifest['files_structure']]),
        )

        conversation_log = [
            {
                'role': 'system',
                'content': self.system_prompt + "\n" + sub_prompt + f"\nMaximum allowed tools calling: {self.MAX_STEP-1}; planing work with this restriction!"
            },
            {
                'role': 'user',
                'content': self.instruction
            }
        ]

        agent_step_counter = 1
        while True:
            if agent_step_counter > self.MAX_STEP:
                logger.warning("MAX_STEP exceed!")
                yield DTOInstruction(type=EventType.ERROR, message="MAX_STEP exceed!")
                break

            is_empty_workaround = False
            while True:
                output = None
                tools_arguments_parsing = {}
                for chunk in llm_query_stream(conversation_log, tools=SUPERVISOR_TOOLS, model_name=specific_model):
                    if chunk['type'] == 'final':
                        output = chunk
                        break
                    elif chunk['type'] == 'tool':
                        _tool_call = chunk['tool_calls'][0]

                        try:
                            tools_arguments_parsing = json.loads(_tool_call['function']['arguments']) if _tool_call['function']['arguments'] else {}
                        except:
                            pass

                        yield DTOInstruction(type=EventType.AGENT, is_final=False, message_id=chunk['id'], function=tools_arguments_parsing.get('agent_name', ''))
                    else:
                        yield DTOInstruction(type=EventType.NOPE)

                if output:
                    break

                if not AVOID_EMPTY_RESPONSE:
                    # == exit
                    logger.info("Empty response. Stop working")
                    return True

                logger.info("Empty response. Force to using tool")

                if not is_empty_workaround:
                    is_empty_workaround = True
                    conversation_log.append({
                        'role': 'user',
                        'content': 'Dont answer with empty message. If you have finished the work - call `exit` tool!'
                    })

            tool_call_description = None
            current_tool_call = None
            for tool_call in output['tool_calls']:
                function_name = tool_call['function']['name']

                tool_call_description = {
                    'function': function_name,
                    'id': tool_call['id'],
                }

                arguments = json.loads(tool_call['function']['arguments']) if tool_call['function']['arguments'] else []

                if function_name == 'call_agent':
                    instruction = arguments.get('instruction', None)
                    agent_name = arguments.get('agent_name', None)
                    tool_call_description['args'] = [agent_name, instruction]
                elif function_name == 'message':
                    tool_call_description['args'] = [arguments.get('text', None)]

                current_tool_call = tool_call
                break

            if not tool_call_description and output['output']:
                conversation_log.append({
                    'role': 'assistant',
                    'content': output['output'],
                })
                self.log(output['output'], True)

                yield DTOInstruction(type=EventType.MARKDOWN, message=output['output'])

                agent_step_counter += 1
                continue

            if not tool_call_description and not output['output']:
                yield DTOInstruction(type=EventType.ERROR, message="Agent call error (empty)")
                break

            self.log(tool_call_description, True)

            agent_complete_report = None
            if tool_call_description['function'] == 'exit':
                yield DTOInstruction(type=EventType.EXIT, message_id=output['id'])
                break
            elif tool_call_description['function'] == 'message':
                yield DTOInstruction(type=EventType.MARKDOWN, message=tool_call_description['args'][0], message_id=output['id'])

                agent_complete_report = 'message print to user'
            elif tool_call_description['function'] == 'call_agent':
                agent_name, agent_instruction = tool_call_description['args']
                if agent_name not in Agent.PROMPTS:
                    yield DTOInstruction(type=EventType.ERROR, message=f"Agent call error (name), name=`{agent_name}`", message_id=output['id'])
                    break

                if not agent_instruction:
                    yield DTOInstruction(type=EventType.ERROR, message=f"Agent call error (empty instruction)", message_id=output['id'])
                    break

                yield DTOInstruction(
                    type=EventType.AGENT,
                    function=agent_name,
                    message=agent_name,
                    args=[agent_name, agent_instruction],
                    message_id=output['id'],
                )

                agent = Agent.fabric(agent_name, self.agent_commands)
                agent.init(agent_instruction, self.manifest, self.LOG_FILE)

                is_agent_completes_work = False
                for agent_step in agent.run():
                    if agent_step.type == 'report':
                        is_agent_completes_work = True
                        agent_complete_report = agent_step.message
                        agent_step.type = 'markdown'
                    elif agent_step.type == 'error':
                        agent_complete_report = 'Agent cant complete a work, try another approach: add more details, rewrite instruction for agent! Agent returns error: ' + agent_step.message
                        is_agent_completes_work = True

                    yield agent_step

                    if is_agent_completes_work:
                        break
            else:
                self.log("ERROR: \n" + pretty_print_as_json(output, truncate=0), True)

                yield DTOInstruction(type=EventType.ERROR, message="Agent call error (wrong tool)", message_id=output['id'])
                break

            if current_tool_call:
                conversation_log.append({
                    'role': 'assistant',
                    'content': output['output'],
                    'tool_calls': [current_tool_call]
                })

                if agent_complete_report:
                    conversation_log.append({
                        'role': 'tool',
                        'tool_call_id': current_tool_call['id'],
                        'name': current_tool_call['function']['name'],
                        'content': agent_complete_report
                    })

            agent_step_counter += 1

    def log(self, data, to_file=False):
        output = pretty_print_as_json(data)
        output = f"[ SUPERVISOR ] {output}"

        if not to_file:
            logger.info(output)
            return

        with open(self.LOG_FILE, "a", encoding='utf8') as f:
            f.write(output + "\n\n")