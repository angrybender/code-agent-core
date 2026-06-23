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


def _split_command_sections(body: str) -> list[str]:
    return re.split(r'(?m)^---\n', body)


def _extract_shell_command(block: str) -> str | None:
    matches = re.findall(r'```[^\n`]*\n(.*?)```|```([^`\n]+)```', block, re.DOTALL)
    commands = [(g1 or g2).strip() for g1, g2 in matches if (g1 or g2).strip()]
    if len(commands) != 1:
        return None
    return commands[0]


def _normalize_shell_block_name(cmd: str, index: int) -> str:
    words = re.sub(r'[^a-zа-яё\d\-_$]+', ' ', cmd.lower())
    words = re.split(r'\s+', words, flags=re.UNICODE)
    words = [_ for _ in words if _]
    if not words:
        words = ["cmd"]

    tokens = words[0].replace('-', '_').strip('_')
    processed = 1
    for w in words[1:]:
        if w[0] == '-' or w[0] == '$' or len(w) == 1:
            continue

        if len(tokens + "_" + w) > 16:
            break

        tokens = tokens + '_' + w
        processed += 1
        if processed == 2:
            break

    tokens = tokens[:16].strip('_')
    return f'{tokens}_{index}'


def _extract_alias(cmd: str) -> tuple[str | None, str]:
    lines = cmd.split('\n')
    alias = None
    cleaned_lines = []
    for line in lines:
        if line.startswith('# '):
            alias_text = line[2:].strip()
            filtered = re.sub(r'[^a-zA-Z0-9 ]', '', alias_text).strip()
            if filtered and alias is None:
                alias = filtered
        else:
            cleaned_lines.append(line)
    cleaned_cmd = '\n'.join(cleaned_lines).strip()
    return alias, cleaned_cmd


def _alias_to_block_name(alias: str, index: int) -> str:
    name = alias.lower().replace(' ', '_')
    name = name[:16].strip('_')
    return f'{name}_{index}'


def _parse_block_args(description: str, cmd: str) -> tuple[str, list[dict]]:
    description_lines = description.splitlines()
    recognized_arg_lines = set()

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
        for line_index, line in enumerate(description_lines):
            m = re.match(r'^\$' + digit + r'\s*[-–]\s*(.+)', line.strip())
            if m:
                arg_desc = m.group(1).strip()
                recognized_arg_lines.add(line_index)
                break
        args.append({'placeholder': f'${digit}', 'description': arg_desc})

    cleaned_description = '\n'.join(
        line for line_index, line in enumerate(description_lines)
        if line_index not in recognized_arg_lines
    ).strip()
    return cleaned_description, args


def parse_agent_commands(directory: str) -> list[dict]:
    if not os.path.isdir(directory):
        return []

    results = []
    pattern = os.path.join(directory, '*.md')
    for filepath in sorted(glob.glob(pattern)):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        post = frontmatter.loads(content)
        body = post.content
        command = os.path.splitext(os.path.basename(filepath))[0]

        config = post.metadata
        if not config:
            config = {}
        config = _parse_command_roles(config)
        if config.get('enabled', True) is False:
            continue

        is_shell = config.get('mcp', False) is False
        if not is_shell:
            continue

        sections = _split_command_sections(body)
        if len(sections) < 2:
            continue

        command_description = sections[0].strip()
        shell_blocks = []
        for block_index, raw_block in enumerate(sections[1:], start=1):
            cmd = _extract_shell_command(raw_block)
            if not cmd:
                continue

            alias, cleaned_cmd = _extract_alias(cmd)
            if alias is not None:
                block_name = _alias_to_block_name(alias, block_index)
            else:
                block_name = _normalize_shell_block_name(cmd, block_index)

            block_description = re.sub(r'```.*?```', '', raw_block, flags=re.DOTALL).strip()
            block_description, block_args = _parse_block_args(block_description, cleaned_cmd)
            shell_blocks.append({
                'name': block_name,
                'description': block_description,
                'cmd': cleaned_cmd,
                'args': block_args,
            })

        if not shell_blocks:
            continue

        results.append({
            'command': command,
            'description': command_description,
            'shell_blocks': shell_blocks,
            'config': config,
        })
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