from commands_helper import execute_terminal_command
#
# r = execute_terminal_command(
#     'docker run -v D:/home/projects/llm-co-pilot/code-agent-core:/app "python:3.12" bash -c "cd /app && pip install -r requirements.txt -q --root-user-action=ignore && bash run_tests.sh"',
#     timeout=120
# )

r = execute_terminal_command(
    'pip install -r requirements.txt -q --root-user-action=ignore && bash run_tests.sh',
    timeout=120
)

print(r)