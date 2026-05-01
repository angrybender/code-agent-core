import base64
import json
import mimetypes
import uuid
import datetime
import os

from agents import BaseAgent
from dto.dto_instruction import DTOInstruction
from dto.enums import EventType
from llm import llm_query_stream, MAX_CONTEXT_WINDOW_SIZE, LLMRequestFormat
from mcp_tool_executor import MCPToolExecutor
from tools.tools import MCP_BASE_TOOLS, TOOL_SUMMARIZE, TOOL_REPORT

MAX_ITERATION = int(os.getenv('MAX_ITERATION'))


class MCPAgent(BaseAgent):
    """
    MCP sub-agent that executes tasks using external MCP (Model Context Protocol) servers.

    Two-phase workflow:
    1. Discovery: Enumerate available MCP servers and their tools, inject summary into context.
    2. Execution: LLM selects a server via select_mcp, then calls MCP tools to complete the task.
    """

    def __init__(self, role: str, system_prompt: str, step_prompt: str, mcp_commands: list):
        """
        :param role: Agent role string (e.g. 'MCP')
        :param system_prompt: System prompt text
        :param step_prompt: Shared project context sub-prompt
        :param mcp_commands: List of legacy MCP command configs loaded via the dedicated helper in mcp_integration/mcp_helper.py
        """
        super().__init__(role, system_prompt, step_prompt, project=None, has_shell_commands=False)
        self.mcp_commands = mcp_commands
        self._mcp_commands_map = {cmd['command']: cmd for cmd in mcp_commands}
        self._selected_server_name = None
        self._selected_mcp_tools = None
        self._mcp_executor = None
        self._mcp_servers_tools = {}

    @staticmethod
    def _encode_image_to_data_url(file_path: str, project_root: str | None = None) -> tuple[str, str | None]:
        if not file_path or not isinstance(file_path, str):
            raise Exception("Invalid path")
        if '\x00' in file_path:
            raise Exception("Invalid path")

        file_path = os.path.normpath(file_path)
        if file_path.startswith('..') or file_path.startswith('/'):
            raise Exception("Invalid path")

        real_path = os.path.realpath(os.path.join(project_root, file_path))
        if not os.path.exists(real_path):
            raise Exception("File not exists")

        mime_type, _ = mimetypes.guess_type(real_path)
        if not mime_type or not mime_type.startswith('image/'):
            return '', 'file is not an image'

        max_size = 5 * 1024 * 1024  # 5 MB
        if os.path.getsize(real_path) > max_size:
            return '', 'file exceeds 5 MB limit'

        with open(real_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('ascii')

        return f'data:{mime_type};base64,{encoded}', None

    def get_tools(self) -> list:
        if self._selected_server_name is not None and self._selected_mcp_tools is not None:
            return self._selected_mcp_tools + MCP_BASE_TOOLS
        return MCP_BASE_TOOLS

    def run(self):
        assert self.instruction, 'init() is required'

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

        self.log("============= INSTRUCTION =============", True)
        self.log(user_content, True)

        conversation = [
            {
                'role': 'system',
                'content': (
                    self.system_prompt + "\n" + sub_prompt
                    + f"\nMaximum allowed tools calling: {MAX_ITERATION - 1}, dont exceed it!"
                )
            },
            {
                'role': 'user',
                'content': user_content,
            }
        ]

        # ── Phase 1: MCP Server Discovery ──────────────────────────────────────────
        status_msg_id = str(uuid.uuid4())
        server_lines = []

        _servers_descriptions = {}
        for server_name, cmd_config in self._mcp_commands_map.items():
            try:
                executor = MCPToolExecutor(server_name, cmd_config)
                tools = []
                for tool in executor.list_tools():
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": tool['name'],
                            "description": tool['description'],
                            "parameters": {
                                "type": "object",
                                "properties": tool['inputSchema']
                            }
                        }
                    })

                executor.close_session()

                self._mcp_servers_tools[server_name] = tools
                server_lines.append(f"- **{server_name}**: {len(tools)} tools")
                yield DTOInstruction(
                    type=EventType.MARKDOWN,
                    message="MCP servers discovered:\n" + "\n".join(server_lines),
                    message_id=status_msg_id,
                    is_final=False,
                )

                _servers_descriptions[server_name] = cmd_config['description']
            except Exception as e:
                self.log(f"[MCPAgent] Failed to load tools from '{server_name}': {e}")

        if server_lines:
            yield DTOInstruction(
                type=EventType.MARKDOWN,
                message="MCP servers discovered:\n" + "\n".join(server_lines),
                message_id=status_msg_id,
                is_final=True,
            )
        else:
            yield DTOInstruction(
                type=EventType.INFO,
                message="No MCP servers available.",
                message_id=status_msg_id,
                is_final=True,
            )

            yield DTOInstruction(
                type=EventType.REPORT,
                message="No MCP servers available.",
                exit=True,
            )
            return

        if self._mcp_servers_tools:
            server_summary_parts = ["## Available MCP Servers\n"]
            for srv_name, srv_tools in self._mcp_servers_tools.items():
                tool_descs = []
                for t in srv_tools:
                    tool_descs.append(f"  - `{t['function']['name']}`: {t['function']['description']}")
                server_summary_parts.append(
                    f"### {srv_name}\n**Description**: {_servers_descriptions[srv_name]}\n**Tools**:\n" + "\n".join(tool_descs)
                )
            server_summary = "\n".join(server_summary_parts)
        else:
            server_summary = "No MCP servers are currently available."

        conversation.append({
            "role": "user",
            "content": server_summary + "\n\nNow please complete the task using the available MCP servers.",
        })

        # ── Phase 2: Execution Loop ─────────────────────────────────────────────────
        agent_step = 0
        _summarize_count = 0
        _context_overflow_summarize = False
        _max_step_workaround = False
        _llm_format_error_workaround = 0

        while True:
            agent_step += 1
            if agent_step > MAX_ITERATION:
                yield DTOInstruction(type=EventType.ERROR, message="MAX_STEP exceed!", exit=True)
                break

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
                            message_id=chunk['id'],
                        )
                    else:
                        yield DTOInstruction(
                            type=EventType.PENDING,
                            message_id=chunk['id'],
                            message=chunk.get('content'),
                            is_final=False,
                        )
            except LLMRequestFormat as e:
                if _llm_format_error_workaround <= 3:
                    _llm_format_error_workaround += 1
                    conversation.pop()
                    if _llm_format_error_workaround > 1:
                        conversation.pop()
                    else:
                        yield DTOInstruction(
                            type=EventType.WARNING,
                            message_id=str(uuid.uuid4()),
                            message=f"LLM error: {e}. Workaround...",
                            is_final=True,
                        )
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
                    context_window={"used": total_context_size, "limit": MAX_CONTEXT_WINDOW_SIZE},
                )

            if not output:
                yield DTOInstruction(type=EventType.REPORT, message="", hidden=True, message_id=message_id, metadata={})
                _report = self.create_report(conversation)
                if _report:
                    _report = conversation[-1]['content']
                else:
                    _report = "I've completed task"
                yield DTOInstruction(type=EventType.REPORT, message=_report, exit=True, hidden=True, message_id=message_id, metadata=self.artifacts)
                return

            self.log('LLM OUTPUT:\n' + output.get('output', ''), True)

            tool_calls = output.get('tool_calls', []) or []
            current_tool_call = None
            tool_call_description = None

            for tool_call in tool_calls:
                _args = self.parse_tool_arguments(tool_call['function']['arguments']) if tool_call['function']['arguments'] else {}
                tool_call_description = {
                    'function': tool_call['function']['name'],
                    'id': tool_call['id'],
                    'args': _args,
                }
                current_tool_call = tool_call
                current_tool_call['function']['arguments'] = json.dumps(_args)
                break

            if not current_tool_call and not output['output']:
                _report = self.create_report(conversation)
                if not _report:
                    _report = "Agent has not completed work, empty response"
                yield DTOInstruction(type=EventType.REPORT, message=_report, exit=True, hidden=True, message_id=message_id, metadata=self.artifacts)
                return
            elif not current_tool_call and output['output']:
                yield DTOInstruction(type=EventType.MARKDOWN, message=output['output'], exit=True)
                conversation.append({'role': 'assistant', 'content': output['output']})
                continue

            self.log(tool_call_description, True)

            conversation.append({
                'role': 'assistant',
                'content': output['output'] if output['output'] else None,
                'tool_calls': [current_tool_call],
            })

            fn_name = tool_call_description['function']
            fn_args = tool_call_description['args'] or {}

            # ── report ──
            if fn_name == 'report':
                yield DTOInstruction(
                    type=EventType.REPORT,
                    message=fn_args.get('text', '') if fn_args else '',
                    exit=True,
                    message_id=output['id'],
                    metadata=self.artifacts,
                )
                break

            # ── summarize ──
            elif fn_name == 'summarize':
                _context_overflow_summarize = False
                _summarize_count += 1

                llm_summary = fn_args.get('text', '') if fn_args else ''
                artifact_summary = self._build_artifact_summary()
                combined_summary = f"{artifact_summary}\n\n## Agent Findings and Progress:\n{llm_summary}"

                conversation = conversation[:3]
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
                    'content': "Continue the work of create report!",
                })

                self.log(f"SUMMARIZE RESULT:\n{combined_summary}", True)

                yield DTOInstruction(
                    type=EventType.MARKDOWN,
                    message=fn_args.get('text', '') if fn_args else '',
                    message_id=output['id'],
                )
                continue

            # ── select_mcp ──
            elif fn_name == 'select_mcp':
                server_name = fn_args.get('server_name', '')
                if server_name not in self._mcp_servers_tools:
                    available = list(self._mcp_servers_tools.keys())
                    tool_result = f"ERROR: Unknown server '{server_name}'. Available: {available}"
                else:
                    self._selected_server_name = server_name
                    self._selected_mcp_tools = self._mcp_servers_tools[server_name]

                    if self._mcp_executor:
                        self._mcp_executor.close_session()

                    self._mcp_executor = MCPToolExecutor(server_name, self._mcp_commands_map[server_name])
                    available_tool_names = [t['function']["name"] for t in self._selected_mcp_tools]
                    tool_result = (
                        f"MCP server '{server_name}' selected. "
                        f"Available tools: {available_tool_names}"
                    )
                    yield DTOInstruction(
                        type=EventType.TOOL,
                        function=fn_name,
                        args={"server_name": server_name},
                        is_final=True,
                        message_id=output['id'],
                    )

                conversation.append({
                    'role': 'tool',
                    'tool_call_id': current_tool_call['id'],
                    'name': fn_name,
                    'content': tool_result,
                })

            # ── attach_image ──
            elif fn_name == 'attach_image':
                path = fn_args.get('path', '')
                data_url, error = self._encode_image_to_data_url(path, self.interpreter.project_root)
                if error:
                    tool_result = f"ERROR: {error}"
                    conversation.append({
                        'role': 'tool',
                        'tool_call_id': current_tool_call['id'],
                        'name': fn_name,
                        'content': tool_result,
                    })
                else:
                    conversation.append({
                        'role': 'tool',
                        'tool_call_id': current_tool_call['id'],
                        'name': fn_name,
                        'content': f"Image attached successfully: {path}",
                    })
                    conversation.append({
                        'role': 'user',
                        'content': [
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url}
                            }
                        ],
                    })
                    yield DTOInstruction(
                        type=EventType.TOOL,
                        function=fn_name,
                        args={"path": path},
                        is_final=True,
                        message_id=output['id'],
                    )

            # ── mcp <tool_name> ──
            elif self._selected_mcp_tools and fn_name in [t['function']["name"] for t in self._selected_mcp_tools]:
                if self._mcp_executor is None:
                    tool_result = "ERROR: No MCP server selected. Call select_mcp first."
                    conversation.append({
                        'role': 'tool',
                        'tool_call_id': current_tool_call['id'],
                        'name': fn_name,
                        'content': tool_result,
                    })
                else:
                    yield DTOInstruction(
                        type=EventType.TOOL,
                        function=f"mcp:{fn_name}",
                        args=fn_args,
                        message_id=output['id'],
                    )

                    result_dict = self._mcp_executor.call_tool(fn_name, fn_args)
                    tool_result = result_dict.get("result", "")
                    is_error = result_dict.get("error", False)

                    self.artifacts['commands_run'].append({
                        'command': fn_name,
                        'status': 'error' if is_error else 'ok',
                    })

                    conversation.append({
                        'role': 'tool',
                        'tool_call_id': current_tool_call['id'],
                        'name': fn_name,
                        'content': str(tool_result),
                    })

            # ── unknown tool ──
            else:
                conversation.append({
                    'role': 'tool',
                    'tool_call_id': current_tool_call['id'],
                    'name': fn_name,
                    'content': f"ERROR: Unknown tool '{fn_name}'",
                })

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

    def __del__(self):
        if self._mcp_executor:
            self._mcp_executor.close_session()