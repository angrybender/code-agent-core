from file_check_helper import file_check

import os
from dotenv import load_dotenv

load_dotenv()

IDE_MCP_HOST=os.getenv('IDE_MCP_HOST')

r = file_check(IDE_MCP_HOST, 'D:/home/projects/test_project', './patched_file.py')

print(r)