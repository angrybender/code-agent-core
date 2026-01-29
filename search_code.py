import glob
import os
import re
import logging
import time

from path_helper import get_relative_path

logger = logging.getLogger('APP')

def _find_subtext(lines: list[str], substr: str) -> tuple[str, float]:
    for line in lines:
        if line.lower().find(substr.lower()) > -1:
            return line, 1.0

    tokens = re.split(r'\W', substr)
    tokens = [_.lower() for _ in tokens]

    candidates = []
    for line in lines:
        _line = line.lower()
        score = 0
        for token in tokens:
            if _line.find(token) > -1:
                score += 1

        if score > 0:
            candidates.append((line, score/len(tokens)))

    if not candidates:
        return '', 0.0

    candidates = sorted(candidates, key=lambda line_score: -line_score[1])
    return candidates[0]


def _detect_code_by_file_name(file_name) -> str:
    ext = file_name.split('.')[-1]

    ext_map = {
        # Common programming languages
        "py": "python",
        "pyi": "python",
        "js": "javascript",
        "mjs": "javascript",
        "cjs": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "jsx": "javascript",
        "java": "java",
        "kt": "kotlin",
        "kts": "kotlin",
        "scala": "scala",
        "go": "golang",
        "rb": "ruby",
        "php": "php",
        "rs": "rust",
        "rust": "rust",
        "swift": "Swift",
        "cs": "csharp",
        "csharp": "csharp",
        "fs": "txt",
        "vb": "txt",
        "c": "c",
        "h": "c",
        "cc": "cpp",
        "cpp": "cpp",
        "cxx": "cpp",
        "hpp": "cpp",
        "hh": "cpp",
        "m": "txt",
        "mm": "txt",
        "r": "txt",
        "jl": "txt",
        "lua": "lua",
        "pl": "txt",
        "pm": "txt",
        "dart": "txt",
        "ex": "elixir",
        "exs": "elixir",
        "erl": "txt",
        "hrl": "txt",
        "hs": "haskell",
        "clj": "txt",
        "cljs": "txt",

        # Shell / scripting
        "sh": "bash",
        "bash": "bash",
        "zsh": "bash",
        "ps1": "txt",
        "bat": "txt",
        "cmd": "txt",

        # Web / markup
        "html": "html",
        "htm": "html",
        "css": "css",
        "scss": "css",
        "sass": "css",
        "less": "css",
        "svg": "txt",
        "md": "txt",

        # Data / config
        "json": "json",
        "yml": "yaml",
        "yaml": "yaml",
        "toml": "txt",
        "ini": "txt",
        "xml": "txt",
        "sql": "txt",
        "graphql": "txt",
        "gql": "txt",
        "txt": "txt",
        "env": "txt",
    }

    return ext_map.get(ext, "")

MAX_RESULTS = 10


class SearchCode:
    def __init__(self):
        self._files_cache = {}

    def reset(self):
        self._files_cache = {}

    def search(self, project_path: str, needle: str, extension: str) -> list[dict]:
        _start_time = time.time()

        extension = extension.strip().strip('*').strip('.')
        if extension:
            mask = f'*.{extension.lower()}'
        else:
            mask = '*'

        file_pattern = os.path.join(project_path, '**', mask)
        files_to_search = glob.glob(file_pattern, recursive=True)
        logger.info(f"[search] total files: {len(files_to_search)}")
        logger.info(f"[search] looking for: `{needle}` (extension: `{extension}`)")

        results = []
        for file_path in files_to_search:
            file_path_relative = get_relative_path(project_path, file_path)

            lang = _detect_code_by_file_name(file_path)
            if lang == '':
                continue

            if file_path in self._files_cache:
                code = self._files_cache[file_path]
            else:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    self._files_cache[file_path] = code
                except:
                    continue

            lines = code.split("\n")

            line, score = _find_subtext(lines, needle)
            if line and score > 0.0:
                results.append({
                    'file': file_path_relative,
                    'found': line.strip(),
                    'score': score
                })

        results = sorted(results, key=lambda r: -r['score'])

        logger.info(f"[search] total found: {len(results)}; total time: {time.time() - _start_time}")
        return results[:MAX_RESULTS]