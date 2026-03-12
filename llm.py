import os
import uuid
import time
import logging
import json

from openai import OpenAI
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

MAX_PROMPT_OUTPUT = os.getenv('MAX_PROMPT_OUTPUT', '')
if MAX_PROMPT_OUTPUT:
    MAX_PROMPT_OUTPUT = int(MAX_PROMPT_OUTPUT)
else:
    MAX_PROMPT_OUTPUT = None


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


def llm_query(messages, tags=None, tools=None, model_name=None):
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
        'max_tokens': MAX_PROMPT_OUTPUT,
        'tools': tools,
    }

    if REASONING_EFFORT:
        options['reasoning_effort'] = REASONING_EFFORT

    for attempt in range(attempts):
        try:
            response = client.chat.completions.create(**options)
            content = response.choices[0].message.content.strip() if response.choices[0].message.content else ''

            logger.debug("OUTPUT:")
            logger.debug(pretty_format(response.choices[0]) + "\n\n")

            if len(content) == 0 and tools and not response.choices[0].message.tool_calls:
                yield None
                break

            if tags:
                output = parse_tags(content, tags)
            else:
                output = {}

            output['_output'] = content
            if tools:
                output['_tool_calls'] = response.choices[0].message.tool_calls
                output['_message'] = response.choices[0].message

                if not output['_tool_calls']:
                    output['_tool_calls'] = []

            yield output
            break
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


def llm_query_stream(messages, tags=None, tools=None, model_name=None):
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

    options = {
        'messages': messages,
        'model': model_name if model_name else MODEL,
        'max_tokens': MAX_PROMPT_OUTPUT,
        'tools': tools,
        'stream': True,
    }

    if REASONING_EFFORT:
        options['reasoning_effort'] = REASONING_EFFORT

    options = {k: v for k, v in options.items() if v is not None}

    error = None
    message_id = str(uuid.uuid4())

    yield {
        "id": message_id,
        "type": "pending",
    }

    pre_parsed_tools = {}
    for attempt in range(5):
        try:
            response = client.chat.completions.create(**options)

            _output = ""
            _tool_calls = {}

            for chunk in response:
                if not chunk.choices:
                    # some reasoning models
                    yield {
                        "id": message_id,
                        "type": "pending",
                    }
                    continue

                choice = chunk.choices[0]

                if choice.delta.content is not None:
                    _output += choice.delta.content

                if choice.delta.tool_calls:
                    for tool_call_delta in choice.delta.tool_calls:
                        idx = tool_call_delta.index
                        if idx not in _tool_calls:
                            _tool_calls[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
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
                    }

            final = {
                "id": message_id,
                "type": "final",
                "output": _output,
                "tool_calls": list(_tool_calls.values())
            }

            if tags:
                final.update(parse_tags(_output, tags))
            yield final
            break
        except Exception as e:
            error = e
            logger.warning(f"Attempt {attempt + 1}: Unexpected error: {e}")
            time.sleep(1)

    if error:
        with open('./conversations_log/llm.error', 'w', encoding='utf8') as f:
            f.write("INPUT: \n" + pretty_format(messages) +"\n\nERROR:\n" + pretty_format(error))

        raise error