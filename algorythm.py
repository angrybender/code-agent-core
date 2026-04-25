import json
import os
import glob
import datetime
import time

from dto.dto_instruction import DTOInstruction
from dto.enums import EventType
from log_helper import pretty_format
import ide_integration
from llm import llm_query_stream, MAX_CONTEXT_WINDOW_SIZE
from path_helper import get_relative_path
from tools_interpreter import ToolsInterpreter
from agents import Agent
from tools.tools import SUPERVISOR_TOOLS
from logger_mixin import LoggerMixin

from commands_helper import parse_agent_commands
from dotenv import load_dotenv
from mcp_integration.mcp_helper import parse_mcp_commands

load_dotenv()

MAX_ITERATION=os.getenv('MAX_ITERATION')

import logging
logger = logging.getLogger('APP')
logging.basicConfig(level=logging.INFO)


class Copilot(LoggerMixin):
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
        self.role = 'SUPERVISOR'
        self.log_file = self.LOG_FILE

        self.system_prompt = ''
        self.prompt = ''
        self.executed_commands = []
        self.agent_step = 0

        self.command_state = []

    def get_manifest(self, project_base_path: str):
        content = ide_integration.tool_call('get_file_text_by_path', {
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
            with open('./prompts/supervisor_system.txt', 'r', encoding='utf8') as f:
                self.system_prompt = f.read()

        if not self.prompt:
            with open('./prompts/step.txt', 'r', encoding='utf8') as f:
                self.prompt = f.read()

        assert self.instruction, 'Empty instruction'

        self.manifest = {
            'base_path': self.session['project_base_path'],
            'description': self.get_manifest(self.session['project_base_path']).strip(),
            'files_structure': self._read_project_structure(self.session['project_base_path']),
        }

        shell_cmd_dir = os.getenv('SHELL_COMMAND_DIRECTORY', '.agent-commands')
        full_cmd_dir = os.path.join(self.session['project_base_path'], shell_cmd_dir)
        self.agent_commands = parse_agent_commands(full_cmd_dir, 'shell')
        self.manifest['agent_commands'] = self.agent_commands
        self.mcp_commands = parse_mcp_commands(full_cmd_dir)
        self.manifest['mcp_commands'] = self.mcp_commands

        self.output = []

        self.executed_commands = []
        self.command_state = []
        self.agent_step = 1
        self.interpreter = ToolsInterpreter(self.session['project_base_path'])

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

        # ping IDE
        start_msg_id = str(time.time())
        yield DTOInstruction(type=EventType.AGENT, is_final=False, message_id=start_msg_id, function="SUPERVISOR")
        ping_mcp = ide_integration.tool_call('__test__connection__', {"projectPath": self.session['project_base_path']})
        if not ping_mcp['result']:
            yield DTOInstruction(type=EventType.ERROR, message_id=start_msg_id, message=f"MCP ide integration error: {ping_mcp['error']}")
            return []
        yield DTOInstruction(type=EventType.AGENT, hidden=True, message_id=start_msg_id, function="SUPERVISOR")

        self.log(str(datetime.datetime.now()), True)
        self.log(f"RUN. Messages: `{self.instruction}`", False)

        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        sub_prompt = self.prompt.format(
            project_description=self.manifest['description'],
            project_structure="\n".join([f"- {path}" for path in self.manifest['files_structure']]),
            current_datetime=current_datetime,
        )

        pending_images = self.session.get('pending_images', []) if self.session else []

        if pending_images:
            user_content = [{"type": "text", "text": self.instruction}]
            for img_url in pending_images:
                user_content.append({"type": "image_url", "image_url": {"url": img_url}})
        else:
            user_content = self.instruction

        conversation_log = [
            {
                'role': 'system',
                'content': self.system_prompt + "\n" + sub_prompt + f"\nMaximum allowed tools calling: {self.MAX_STEP-1}; planing work with this restriction!"
            },
            {
                'role': 'user',
                'content': user_content
            }
        ]

        agent_step_counter = 1
        while True:
            if agent_step_counter > self.MAX_STEP:
                logger.warning("MAX_STEP exceed!")
                yield DTOInstruction(type=EventType.ERROR, message="MAX_STEP exceed!")
                break

            output = None
            message_id = None
            for chunk in llm_query_stream(conversation_log, tools=SUPERVISOR_TOOLS, model_name=specific_model, force_tool=True):
                message_id = chunk['id']
                if chunk['type'] == 'final':
                    output = chunk
                    break
                elif chunk['type'] == 'tool':
                    _tool_call = chunk['tool_calls'][0]
                    tools_arguments_parsing = _tool_call['function']['arguments_parsed'] if _tool_call['function'].get('arguments_parsed') else {}
                    agent_name = tools_arguments_parsing.get('agent_name', '')
                    if agent_name:
                        yield DTOInstruction(type=EventType.AGENT, is_final=False, message_id=chunk['id'], function=agent_name)
                else:
                    yield DTOInstruction(type=EventType.AGENT, is_final=False, message_id=chunk['id'], function="SUPERVISOR")

            _prompt_tokens = output.get('tokens_usage', {}).get('prompt', 0)
            if _prompt_tokens > 0:
                yield DTOInstruction(
                    type=EventType.CONTEXT,
                    context_window={"used": _prompt_tokens + output['tokens_usage']['completion'], "limit": MAX_CONTEXT_WINDOW_SIZE}
                )

            if not output:
                logger.info("Empty response. Stop working")
                yield DTOInstruction(type=EventType.REPORT, message="", hidden=True, message_id=message_id)
                return True

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
                    agent_images = arguments.get('images', [])
                    if not isinstance(agent_images, list):
                        agent_images = []
                    # Resolve integer image indices to real base64 Data URLs from pending_images
                    resolved_images = []
                    if agent_images and pending_images:
                        for idx in agent_images:
                            if isinstance(idx, int):
                                real_idx = idx - 1  # convert 1-based to 0-based
                                if 0 <= real_idx < len(pending_images):
                                    resolved_images.append(pending_images[real_idx])
                            # invalid or out-of-range indices are silently skipped
                    tool_call_description['args'] = [agent_name, instruction, resolved_images]
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
                # cycle stop correct (modern LLM just stop generation if it has decided to finish)
                break

            self.log(tool_call_description, True)

            agent_complete_report = None
            last_agent_metadata = None
            if tool_call_description['function'] == 'exit':
                yield DTOInstruction(type=EventType.EXIT, message_id=output['id'])
                break
            elif tool_call_description['function'] == 'message':
                yield DTOInstruction(type=EventType.MARKDOWN, message=tool_call_description['args'][0], message_id=output['id'])

                agent_complete_report = 'message print to user'
            elif tool_call_description['function'] == 'call_agent':
                last_agent_metadata = None
                agent_name, agent_instruction, agent_images = tool_call_description['args']
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

                agent = Agent.create(agent_name, self.agent_commands, mcp_commands=self.manifest.get('mcp_commands', []))
                agent.init(agent_instruction, self.manifest, self.LOG_FILE, images=agent_images)

                is_agent_completes_work = False
                for agent_step in agent.run():
                    if agent_step.type == EventType.REPORT:
                        is_agent_completes_work = True
                        agent_complete_report = agent_step.message
                        last_agent_metadata = agent_step.metadata
                        agent_step.type = EventType.MARKDOWN
                    elif agent_step.type == EventType.ERROR:
                        agent_complete_report = 'Agent cant complete a work, try another approach: add more details, rewrite instruction for agent! Agent returns error: ' + agent_step.message
                        is_agent_completes_work = True

                    yield agent_step

                    if is_agent_completes_work:
                        break

                del agent
            else:
                self.log("ERROR: \n" + pretty_format(output, truncate=0), True)

                yield DTOInstruction(type=EventType.ERROR, message="Agent call error (wrong tool)", message_id=output['id'])
                break

            if current_tool_call:
                conversation_log.append({
                    'role': 'assistant',
                    'content': output['output'] if output['output'] else None,
                    'tool_calls': [current_tool_call]
                })

                if agent_complete_report:
                    enriched_report = agent_complete_report
                    if last_agent_metadata:
                        summary_parts = []
                        if last_agent_metadata.get('files_created'):
                            summary_parts.append("Files created:\n" + "\n".join(f"- {f}" for f in last_agent_metadata['files_created']))
                        if last_agent_metadata.get('files_modified'):
                            summary_parts.append("Files modified:\n" + "\n".join(f"- {f}" for f in last_agent_metadata['files_modified']))
                        if last_agent_metadata.get('commands_run'):
                            summary_parts.append("Commands executed:\n" + "\n".join(
                                f"- {c['command']} ({c['status']})" for c in last_agent_metadata['commands_run']
                            ))
                        if summary_parts:
                            enriched_report += "\n\n---\n## Structured Artifacts\n" + "\n".join(summary_parts)

                    self.log(f"Agent report: \n{pretty_format(enriched_report)}", True)

                    conversation_log.append({
                        'role': 'tool',
                        'tool_call_id': current_tool_call['id'],
                        'name': current_tool_call['function']['name'],
                        'content': enriched_report or 'Agent did not return a report.'
                    })

            agent_step_counter += 1