dto = {
    'message': str,
    'type': str,
    'files': [
        {
            'file_path': str,
            'file_name': str,
            'payload': dict,
        }
    ]
}

class DTO:
    def __init__(self):
        self._data = {}
        self._message = ""
        self._files = {}

    def setMessage(self, message: str):
        self._message = message
        return self

    def setFiles(self, files: list[dict]):
        self._files = files
        return self

    def serialize(self) -> dict:
        return self._data

class Error(DTO):
    pass

class Nope(DTO):
    pass