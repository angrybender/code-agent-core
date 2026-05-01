import os.path

from ide_integration import tool_call
from search_code import SearchCode


class Project:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.files_history = []
        self.search_service = SearchCode()

    def get_project_root(self) -> str:
        return self.project_root

    def read_file(self, path: str):
        content = tool_call('get_file_text_by_path', {
            'pathInProject': path,
            'projectPath': self.project_root,
        })

        return {
            'content': content.get('status', None),
            'error': content.get('error', None),
        }

    def write_file(self, path: str, content: str):
        content_before = self.read_file(path)
        if content_before['content']:
            content_before = content_before['content']
        else:
            content_before = ''

        abs_path = os.path.join(self.project_root, path)
        version = len(self.files_history)
        self.files_history.append({
            'path': abs_path,
            'content': content_before,
            'version': version + 1
        })

        mcp_result = tool_call('create_new_file', {
            'pathInProject': path,
            'text': content,
            'projectPath': self.project_root,
            'overwrite': True,
        })

        self.files_history.append({
            'path': abs_path,
            'content': content,
            'version': version + 2
        })

        self.search_service.reset()

        return {
            'result': mcp_result.get('status', None),
            'error': mcp_result.get('error', None),
        }

    def get_current_version(self) -> int:
        return len(self.files_history)

    def get_files_history(self, start_version: int, end_version: int) -> list[dict]:
        files_history_result = {}
        if end_version == -1:
            end_version = self.get_current_version()

        for file in self.files_history:
            if start_version <= file['version'] <= end_version:
                if file['path'] not in files_history_result:
                    files_history_result[file['path']] = [file, None]
                else:
                    files_history_result[file['path']][1] = file

        for path, versions in files_history_result.items():
            files_history_result[path] = [_ for _ in versions if _]

        return list(files_history_result.values())

    def get_file_history(self, path: str) -> list[dict]:
        abs_path = os.path.join(self.project_root, path)
        history = []
        for file in self.files_history:
            if file['path'] == abs_path:
                history.append(file)

        return history

    def search_files(self, needle: str, extension: str) -> tuple[int, list[dict]]:
        return self.search_service.search(self.project_root, needle, extension)