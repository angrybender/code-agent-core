import os
import re
import subprocess

def parse_agent_commands(directory: str) -> list[dict]:
    if not os.path.isdir(directory):
        return []

    results = []
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith('.md'):
            continue
        filepath = os.path.join(directory, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        blocks = re.findall(r'```[^\n`]*\n(.*?)```|```([^`\n]+)```', content, re.DOTALL)
        cmd_parts = [g1 or g2 for g1, g2 in blocks]
        if not cmd_parts:
            continue
        cmd = cmd_parts[-1].strip()
        if not cmd:
            continue
        description = re.sub(r'```.*?```', '', content, flags=re.DOTALL).strip()
        command = os.path.splitext(filename)[0]
        results.append({'command': command, 'description': description, 'cmd': cmd})
    return results

def execute_terminal_command(cmd: str, timeout: int, cwd: str = None) -> dict:
    """
    Execute a shell command and return its output.

    Args:
        cmd: Shell command string to execute (e.g. 'ls -la ./').
        timeout: Maximum allowed execution time in seconds.
        cwd: Working directory for the command. Defaults to None (inherits current process directory).

    Returns:
        dict with keys:
            'stdout' (str)  – standard output of the command
            'stderr' (str)  – standard error of the command
            'status' (str)  – 'ok', 'timeout', or 'error'
    """
    try:
        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        status = 'ok' if result.returncode == 0 else 'error'
        stdout = result.stdout or ''
        stderr = result.stderr or ''
        if status == 'ok' and not stdout and stderr:
            stdout = stderr
            stderr = ''
        return {'stdout': stdout, 'stderr': stderr, 'status': status}

    except subprocess.TimeoutExpired as e:
        return {
            'stdout': e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or ''),
            'stderr': e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or ''),
            'status': 'timeout',
        }
    except Exception as e:
        return {'stdout': '', 'stderr': str(e), 'status': 'error'}