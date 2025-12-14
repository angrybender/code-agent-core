from pathlib import Path

def get_relative_path(project_root: str, path: str) -> str:
    project_root = project_root.replace('\\', '/')
    path = path.replace('\\', '/')
    absolute_path = Path(project_root)
    return str(Path(path).relative_to(absolute_path)).replace('\\', '/')