import os
import re
import uuid
import time
import logging
import json

from openai import OpenAI, BadRequestError, APIError
from dotenv import load_dotenv

from llm_parser import parse_tags
from log_helper import pretty_format

# Load environment variables from .env file
load_dotenv()

# setup logger
IS_DEBUG = int(os.environ.get('DEBUG', 0)) == 1
if IS_DEBUG:
    logger = logging.getLogger('llm_api')
    logger.setLevel(logging.DEBUG)

    # create file handler which logs even debug messages
    fh = logging.FileHandler('./conversations_log/full_log.log')
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
else:
    logger = logging.getLogger('APP')

# Constants for OpenAI API configuration
API_URL = os.getenv('OPENAI_API_URL')
API_KEY = os.getenv('OPENAI_API_KEY')
API_TIMEOUT = int(os.getenv('OPENAI_API_TIMEOUT'))
MODEL = os.getenv('MODEL')
REASONING_EFFORT = os.getenv('REASONING_EFFORT')
MAX_CONTEXT_WINDOW_SIZE = int(os.getenv('MAX_CONTEXT_WINDOW_SIZE', 100000))


class ContextOverflow(Exception):
    pass

class LLMRequestFormat(Exception):
    # errors about wrong tooling calls, wrong messages format etc
    pass


def _sanitise_json_string(s: str) -> str:
    """
    Best-effort fix for JSON strings that contain unescaped double-quotes
    or bare control characters (newlines, tabs, etc.) inside string values.
    """
    result = []
    in_string = False
    i = 0
    while i < len(s):
        ch = s[i]
        if in_string:
            if ch == '\\':
                result.append(ch)
                i += 1
                if i < len(s):
                    result.append(s[i])
                    i += 1
                continue
            elif ch == '"':
                in_string = False
                result.append(ch)
            elif ch == '\n':
                result.append('\\n')
            elif ch == '\r':
                result.append('\\r')
            elif ch == '\t':
                result.append('\\t')
            else:
                result.append(ch)
        else:
            if ch == '"':
                in_string = True
                result.append(ch)
            else:
                result.append(ch)
        i += 1
    return ''.join(result)


def _parse_json(json_str: str):
    if not isinstance(json_str, str):
        return None

    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        pass

    sanitised = _sanitise_json_string(json_str)

    try:
        return json.loads(sanitised)
    except (json.JSONDecodeError, ValueError):
        pass

    closers = ["}", '"}', "]", '"]']
    for i in range(len(sanitised), 0, -1):
        _json_str = sanitised[:i]
        for closer in closers:
            try:
                return json.loads(_json_str + closer)
            except (json.JSONDecodeError, ValueError):
                pass

    return None


def llm_query(messages, tags=None, tools=None, model_name=None, max_tokens=None) -> dict|None:
    """
    :param messages:
    :param tags:
    :param tools:
    :param model_name:
    :return:
    """
    client = OpenAI(
        api_key=API_KEY,
        base_url=API_URL,
        timeout=API_TIMEOUT,
    )

    if type(messages) is str:
        messages = [
            {
                'role': 'user',
                'content': messages,
            }
        ]

    logger.debug(f"INPUT (with tools: {'Y' if tools else 'N'}):")
    for m in messages:
        logger.debug(m)

    attempts = 5
    response = None
    error = None

    options = {
        'messages': messages,
        'model': model_name if model_name else MODEL,
        'tools': tools,
    }

    if max_tokens:
        options['max_tokens'] = max_tokens

    if REASONING_EFFORT:
        options['reasoning_effort'] = REASONING_EFFORT

    for attempt in range(attempts):
        try:
            response = client.chat.completions.create(**options)
            content = response.choices[0].message.content.strip() if response.choices[0].message.content else ''

            logger.debug("OUTPUT:")
            logger.debug(pretty_format(response.choices[0]) + "\n\n")

            if len(content) == 0 and tools and not response.choices[0].message.tool_calls:
                return None

            if tags:
                output = parse_tags(content, tags)
            else:
                output = {}

            output['_output'] = content
            output['_usage'] = response.usage
            if tools:
                output['_tool_calls'] = response.choices[0].message.tool_calls
                output['_message'] = response.choices[0].message

                if not output['_tool_calls']:
                    output['_tool_calls'] = []

            return output
        except APIError as e:
            raise LLMRequestFormat(str(e)) from e

        except Exception as e:
            error = e
            logger.warning(f"Attempt {attempt + 1}: Unexpected error: {e}")
            if response:
                logger.warning(response)
            time.sleep(1)

    if error:
        with open('./conversations_log/llm.error', 'w', encoding='utf8') as f:
            f.write("INPUT: \n" + pretty_format(messages) +"\n\nERROR:\n" + pretty_format(error))

        raise error

def _calculate_tokens_usage_workaround(messages: list[dict], model_name: str) -> int:
    cache_model_name = re.sub(r'[^a-z\d\-]+', '_', model_name, flags=re.IGNORECASE)
    assert messages, 'Empty messages'
    stat_cache = f'./storage/calculate_tokens_usage_workaround_{cache_model_name}.json'

    tokens_per_char = None
    if os.path.exists(stat_cache):
        with open(stat_cache, 'r', encoding='utf8') as f:
            stat = json.load(f)
            if 'tokens_per_char' in stat:
                tokens_per_char = stat['tokens_per_char']

    if not tokens_per_char:
        # calculate statistic for token usage
        _messages = messages[:1]
        _messages[0]['role'] = 'user' # models required at least once users' message
        char_size = len(json.dumps(_messages))
        test_response = llm_query(_messages, model_name=model_name, max_tokens=1)
        assert '_usage' in test_response, 'Wrong response or empty response'
        tokens_usage = test_response['_usage'].prompt_tokens
        tokens_per_char = round(tokens_usage/char_size, 3)

        with open(stat_cache, 'w', encoding='utf8') as f:
            json.dump({"tokens_per_char": tokens_per_char}, f)

    # approximate tokens by full conversation:
    char_size = len(json.dumps(messages))

    return int(round(char_size*tokens_per_char))

def llm_query_stream(messages, tags=None, tools=None, model_name=None, force_tool=False):
    client = OpenAI(
        api_key=API_KEY,
        base_url=API_URL,
        timeout=API_TIMEOUT,
    )

    if type(messages) is str:
        messages = [{'role': 'user', 'content': messages}]

    logger.debug(f"INPUT (with tools: {'Y' if tools else 'N'}):")
    for m in messages:
        logger.debug(m)

    # waiting for a supports in the llama.cpp
    if tools and len(tools) > 1 and force_tool:
        tool_choice = 'required'
    elif tools and len(tools) == 1 and force_tool:
        tool_choice = {"type": "function", "name": tools[0]['function']['name']}
    else:
        tool_choice = 'auto'

    tool_choice = 'auto'

    options = {
        'messages': messages,
        'model': model_name if model_name else MODEL,
        'tools': tools,
        'stream': True,
        'tool_choice': tool_choice
    }

    if REASONING_EFFORT:
        options['reasoning_effort'] = REASONING_EFFORT

    options = {k: v for k, v in options.items() if v is not None}

    error = None
    message_id = str(uuid.uuid4())

    yield {
        "id": message_id,
        "type": "pending",
        "content": "prompt eval..."
    }

    pre_parsed_tools = {}
    sleep_time = 1
    for attempt in range(5):
        try:
            response = client.chat.completions.create(**options)

            _output = ""
            _tool_calls = {}
            _tokens_usage = {}

            for chunk in response:
                if not chunk.choices:
                    # some reasoning models
                    yield {
                        "id": message_id,
                        "type": "pending",
                        "content": "thinking..."
                    }
                    continue

                choice = chunk.choices[0]

                if choice.delta.content is not None:
                    _output += choice.delta.content

                    yield {
                        "id": message_id,
                        "type": "pending",
                        "content": "generating..."
                    }

                if choice.delta.tool_calls:
                    for tool_call_delta in choice.delta.tool_calls:
                        idx = tool_call_delta.index
                        if idx not in _tool_calls:
                            _tool_calls[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}, "_position": len(_tool_calls)}
                        tc = _tool_calls[idx]
                        if tool_call_delta.id:
                            tc["id"] += tool_call_delta.id
                        if tool_call_delta.function and tool_call_delta.function.name:
                            tc["function"]["name"] += tool_call_delta.function.name
                        if tool_call_delta.function and tool_call_delta.function.arguments:
                            tc["function"]["arguments"] += tool_call_delta.function.arguments

                if _tool_calls:
                    for _id, tool in _tool_calls.items():
                        if _id not in pre_parsed_tools:
                            pre_parsed_tools[_id] = tool

                        _args = _parse_json(tool['function']['arguments']) if tool['function']['arguments'] else {}
                        if _args:
                            pre_parsed_tools[_id]['function']['arguments_parsed'] = _args

                    if pre_parsed_tools:
                        yield {
                            "id": message_id,
                            "type": "tool",
                            "output": _output,
                            "tool_calls": list(pre_parsed_tools.values())
                        }
                    else:
                        yield {
                            "id": message_id,
                            "type": "pending",
                            "content": "tool..."
                        }


                if chunk.usage:
                    _tokens_usage = {"prompt": chunk.usage.prompt_tokens, "completion": chunk.usage.completion_tokens}

            if not _tokens_usage:
                _tokens_usage = {
                    "prompt": _calculate_tokens_usage_workaround(messages, options['model']),
                    "completion": _calculate_tokens_usage_workaround([{"content": _output, "tool_calls": _tool_calls}], options['model']),
                }

            final = {
                "id": message_id,
                "type": "final",
                "output": _output,
                "tool_calls": sorted(list(_tool_calls.values()), key=lambda _: _['_position']),
                "tokens_usage": _tokens_usage,
            }

            if tags:
                final.update(parse_tags(_output, tags))
            yield final
            break
        except BadRequestError as e:
            message = str(e)

            if "Assistant response prefill is incompatible with enable_thinking" in message:
                logger.error("Fix: Request ends with assistant prefill while enable_thinking=True, return empty")

                ## api caller must deside workaround own logic depends
                yield {
                    "id": message_id,
                    "type": "final",
                    "output": "",
                    "tool_calls": [],
                    "tokens_usage": {},
                }
            elif "System message must be at the beginning" in message and messages[-1]['role'] == 'system':
                logger.error("Fix: Model doesnt support several system messages")
                messages[-1]['role'] = 'user'
            else:
                raise LLMRequestFormat(message) from e

        except APIError as e:
            raise LLMRequestFormat(str(e)) from e

        except Exception as e:
            error = e
            logger.warning(f"Attempt {attempt + 1}: Unexpected error: {e}")
            time.sleep(sleep_time)
            sleep_time *= 2

    if error:
        with open('./conversations_log/llm.error.log', 'w', encoding='utf8') as f:
            f.write("INPUT: \n" + pretty_format(messages) +"\n\nERROR:\n" + pretty_format(error))

        raise error