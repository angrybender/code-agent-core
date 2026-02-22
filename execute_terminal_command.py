import subprocess

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