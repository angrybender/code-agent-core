import os
from pathlib import Path

def get_relative_path(project_root: str, path: str) -> str:
    project_root = project_root.replace('\\', '/')
    path = path.replace('\\', '/')
    absolute_path = Path(project_root)
    try:
        return str(Path(path).relative_to(absolute_path)).replace('\\', '/')
    except ValueError:
        return path

def ls_la(absolute_path: str) -> list[dict]:
    result = []
    for _path in os.listdir(str(absolute_path)):
        full_path = os.path.join(absolute_path, _path)
        if os.path.isdir(full_path):
            try:
                file_count = sum(len(files) for _, _, files in os.walk(full_path, followlinks=False))
                result.append({
                    'line': f"- {_path}/ (total {file_count} files)"
                })
            except (PermissionError, OSError):
                pass
        else:
            file_size = os.path.getsize(full_path)
            try:
                with open(full_path, 'rb') as f:
                    line_count = f.read().count(b'\n')

                lines_str = f"{line_count} lines" if line_count is not None else "? lines"
                result.append({
                    'line': f"- {_path} ({file_size} bytes, {lines_str})"
                })
            except (PermissionError, OSError):
                pass

    return result
