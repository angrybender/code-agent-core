import os
from openai import OpenAI
from dotenv import load_dotenv
import time
from llm_parser import parse_tags

import logging

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


def llm_query(messages, tags=None, tools=None) -> dict|None:
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

    for message in messages:
        if message['role'] == 'system':
            message['role'] = 'developer'

    if REASONING_EFFORT:
        messages = [{'role': 'system', 'content': f'Reasoning: {REASONING_EFFORT}'}] + messages

    logger.debug(f"INPUT (with tools: {'Y' if tools else 'N'}):")
    for m in messages:
        logger.debug(m)

    attempts = 5
    response = None
    error = None

    options = {
        'messages': messages,
        'model': MODEL,
        'max_tokens': MAX_PROMPT_OUTPUT,
        'tools': tools,
    }

    # if REASONING_EFFORT:
    #     options['reasoning_effort'] = REASONING_EFFORT

    for attempt in range(attempts):
        try:
            response = client.chat.completions.create(**options)
            content = response.choices[0].message.content.strip() if response.choices[0].message.content else ''

            ## TODO DEBUG {
            logger.debug("RESPONSE:")
            logger.debug(response)
            ## TODO DEBUG }

            if len(content) == 0 and tools and not response.choices[0].message.tool_calls:
                return None

            if tags:
                output = parse_tags(content, tags)
            else:
                output = {}

            output['_output'] = content.split('<|end|>')[-1]
            if tools:
                output['_tool_calls'] = response.choices[0].message.tool_calls
                output['_message'] = response.choices[0].message

                if not output['_tool_calls']:
                    output['_tool_calls'] = []

            logger.debug("OUTPUT:")
            logger.debug(output)

            return output
        except Exception as e:
            error = e
            logger.warning(f"Attempt {attempt + 1}: Unexpected error: {e}")
            if response:
                logger.warning(response)
            time.sleep(1)

    if error:
        raise error