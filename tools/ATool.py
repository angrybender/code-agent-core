import os

from abc import abstractmethod, ABC

from dto.dto_tools import DTOTool
from project import Project

class ATool(ABC):
    def __init__(self, shell_tools: dict = None, project: Project = None):
        self.project_root = project.get_project_root()
        self._shell_tools = shell_tools
        self.project = project

    def _validate_path(self, path: str) -> bool:
        if path == '.' or path == '':
            return True

        if not path or not isinstance(path, str):
            return False
        if '\x00' in path:
            return False
        normalized = os.path.normpath(path)
        if normalized.startswith('..') or normalized.startswith('/'):
            return False

        real_path = os.path.realpath(os.path.join(self.project_root, normalized))
        return real_path.startswith(os.path.realpath(self.project_root) + os.sep)

    @staticmethod
    @abstractmethod
    def get_description() -> dict:
        pass

    @staticmethod
    @abstractmethod
    def get_parameters() -> dict:
        pass

    @abstractmethod
    def exec(self, **kwargs) -> DTOTool:
        pass