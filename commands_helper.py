import os
import glob
import re
import subprocess
import sys

import frontmatter

from dto.enums import AgentRole


def _parse_command_roles(config: dict) -> dict:
    raw_role = config.get('role')
    if raw_role is None:
        return config

    if isinstance(raw_role, str):
        roles = [role.strip() for role in raw_role.split(',') if role.strip()]
    else:
        raise ValueError('Command role must be a comma-separated string')

    valid_roles = {role.value for role in AgentRole}
    invalid_roles = [role for role in roles if role not in valid_roles or role == AgentRole.MCP.value]
    if invalid_roles:
        raise ValueError(f"Invalid command role(s): {', '.join(invalid_roles)}")

    config = dict(config)
    config['role'] = roles
    return config


def parse_agent_commands(directory: str, type_command: str = 'shell') -> list[dict]:
    assert type_command in ['shell', 'mcp'], f'Unknown type={type_command}'

    if not os.path.isdir(directory):
        return []

    results = []
    pattern = os.path.join(directory, '*.md')
    for filepath in sorted(glob.glob(pattern)):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        post = frontmatter.loads(content)
        body = post.content
        blocks = re.findall(r'```[^\n`]*\n(.*?)```|```([^`\n]+)```', body, re.DOTALL)
        cmd_parts = [g1 or g2 for g1, g2 in blocks]
        command = os.path.splitext(os.path.basename(filepath))[0]

        if not cmd_parts:
            continue

        cmd = cmd_parts[-1].strip()
        if not cmd:
            continue

        description = re.sub(r'```.*?```', '', body, flags=re.DOTALL).strip()
        description_lines = description.splitlines()
        recognized_arg_lines = set()
        config = post.metadata
        if not config:
            config = {}
        config = _parse_command_roles(config)
        if config.get('enabled', True) is False:
            continue

        is_mcp = config.get('mcp', False) is True
        if type_command == 'mcp' and not is_mcp:
            continue
        if type_command == 'shell' and is_mcp:
            continue

        placeholder_digits = sorted(set(re.findall(r'\$(\d+)', cmd)), key=lambda x: int(x))
        if placeholder_digits:
            expected = [str(i) for i in range(1, len(placeholder_digits) + 1)]
            if placeholder_digits != expected:
                raise ValueError(
                    f"Command argument placeholders must be a contiguous sequence starting at $1, "
                    f"but got: {', '.join('$' + d for d in placeholder_digits)}"
                )
        args = []
        for digit in placeholder_digits:
            arg_desc = ''
            for index, line in enumerate(description_lines):
                m = re.match(r'^\$' + digit + r'\s*[-–]\s*(.+)', line.strip())
                if m:
                    arg_desc = m.group(1).strip()
                    recognized_arg_lines.add(index)
                    break
            args.append({'placeholder': f'${digit}', 'description': arg_desc})

        description = '\n'.join(
            line for index, line in enumerate(description_lines)
            if index not in recognized_arg_lines
        ).strip()

        results.append({'command': command, 'description': description, 'cmd': cmd, 'args': args, 'config': config})
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
        shell = sys.platform != "win32"
        result = subprocess.run(
            cmd,
            shell=shell,
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