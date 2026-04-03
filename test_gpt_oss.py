# Импортируем все необходимые классы
from openai_harmony import (
    HarmonyEncodingName,
    Role,
    load_harmony_encoding
)

# 1. Загружаем специальный кодировщик для gpt-oss
encoding = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)


import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Constants for OpenAI API configuration
API_URL = os.getenv('OPENAI_API_URL')
API_KEY = os.getenv('OPENAI_API_KEY')
API_TIMEOUT = int(os.getenv('OPENAI_API_TIMEOUT'))
MODEL = os.getenv('MODEL')
REASONING_EFFORT = os.getenv('REASONING_EFFORT')


client = OpenAI(
    api_key=API_KEY,
    base_url=API_URL,
    timeout=API_TIMEOUT,
)

Role.DEVELOPER

messages = [
    {
        'role': 'system',
        'content': 'Something. Reasoning: low',
    },
    {
        'role': 'user',
        'content': 'Сколько студентов в мире?',
    }
]

options = {
    'messages': messages,
    'model': MODEL,
}

response = client.chat.completions.create(**options)
#print(response)
content = response.choices[0].message.content.strip() if response.choices[0].message.content else ''
print(content)

# m_content = Message.from_role_and_content(Role.ASSISTANT, content)
# tokens = encoding._inner.render(content, render_options={})
# parsed_response = encoding.parse_messages_from_completion_tokens(tokens, Role.ASSISTANT)
#
# for message in parsed_response:
#     print(f"----- Channel: {message.channel} -----")
#     if message.recipient:
#         print(f"Recipient: {message.recipient}")
#     print(message.content)