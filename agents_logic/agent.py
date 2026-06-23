import logging
import os
import uuid

from dotenv import load_dotenv

from context_helper import compact_conversation_remove_redundant
from llm import llm_query_stream, LLMRequestFormat, MAX_CONTEXT_WINDOW_SIZE
from logger_mixin import LoggerMixin
from conversation_mixin import ConversationMixin
from tools_mixin import ToolsMixin
from tools.fabric import ToolsFabric
from dto.dto_instruction import DTOInstruction
from dto.enums import EventType


load_dotenv()

IDE_MCP_HOST=os.getenv('IDE_MCP_HOST')
MAX_ITERATION=int(os.getenv('MAX_ITERATION'))

logger = logging.getLogger('APP')


class BaseAgent(LoggerMixin, ConversationMixin, ToolsMixin):
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

                return "; ".join([f'{m['tool_calls'][0]['function']['name']}:{m['args'][0] if m['args'] else ''}' for m in tools_list])

            logger.info(
                "Conv context! Before: " + _create_log(conversation) + " After: " + _create_log(
                    new_conversation)
            )

        return new_conversation

    def run(self, system_prompt: str, user_prompt: str, images: list[str], available_tools: list[str], specific_model: None|str):
        all_tools = ToolsFabric.get_all_tools()
        tools_for_model = []
        for tool in all_tools:
            if tool['name'] in available_tools:
                tools_for_model.append(tool)

        if not specific_model:
            specific_model = None

        if images:
            user_content = [{"type": "text", "text": user_prompt}]
            for img in images:
                user_content.append({"type": "image_url", "image_url": {"url": img}})
        else:
            user_content = user_prompt

        conversation = [
            {
                'role': 'system',
                'content': system_prompt + f"\nMaximum allowed tools calling: {MAX_ITERATION - 1}, dont exceed it!"
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
        llm_format_error_workaround = 0
        while agent_step <= MAX_ITERATION:
            agent_step += 1

            conversation = self.conversation_filter(conversation)
            assert conversation, 'Empty conversation'

            yield DTOInstruction(type=EventType.NOPE)

            output = None
            message_id = None
            try:
                for chunk in llm_query_stream(conversation, tools=tools_for_model, model_name=specific_model):
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
                if llm_format_error_workaround <= 3:
                    llm_format_error_workaround += 1
                    conversation.pop()
                    if llm_format_error_workaround > 1:
                        conversation.pop()  # remove instruction below
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
                    context_window={"used": total_context_size, "limit": MAX_CONTEXT_WINDOW_SIZE, "cached": _prompt_tokens.get('cached_tokens', 0)}
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

                yield DTOInstruction(type=EventType.REPORT, message=_report, exit=True, hidden=True, message_id=message_id, metadata={})
                return

            tool_calls = output.get('tool_calls', [])
            if tool_calls:
                current_tool_call = tool_calls[-1]
            else:
                current_tool_call = None

