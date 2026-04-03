import os
import os.path
import re
import json
import shlex
import hashlib

from commands_helper import execute_terminal_command

from diff_helper import apply_patch, PatchError
from mcp_helper import tool_call
from search_code import SearchCode

from dotenv import load_dotenv

load_dotenv()

START_PORT = 64342
END_PORT = 64999
EXPECT_ID = '31DSsrohycGMjnclo58RfrhPQzk'
for mcp_port in range(START_PORT, END_PORT):
    print(f'PORT={mcp_port}')
    try:
        file = tool_call(f'http://127.0.0.1:{mcp_port}/sse', 'mcp:get_file_text_by_path', {
            'pathInProject': '.idea/workspace.xml',
            'projectPath': 'D:\home\projects\llm-co-pilot\code-agent-jetbrains-plugin'
            #'projectPath': 'D:\home\projects\llm-co-pilot\code-agent-core'
        })

        projectId = re.findall(r'<component name="ProjectId" id="(.+)"', file.get('status', ''))

        if projectId:
            print('projectId:', projectId[0], f' port: {mcp_port}')
            break
    except:
        pass