import glob
import os
import re
import logging
import time

from path_helper import get_relative_path

logger = logging.getLogger('APP')

def _truncate_line_around_match(line: str, match_pos: int, max_chars: int = 1000) -> str:
    if len(line) <= max_chars:
        return line

    half_window = max_chars // 2
    start = max(0, match_pos - half_window)
    end = min(len(line), match_pos + half_window)

    if start == 0:
        end = min(len(line), max_chars)
    elif end == len(line):
        start = max(0, len(line) - max_chars)

    return '...' + line[start:end] + '...'


def _find_subtext(lines: list[str], substr: str) -> tuple[str, int, float]:
    for line_index, line in enumerate(lines):
        pos = line.lower().find(substr.lower())
        if pos > -1:
            truncated_line = _truncate_line_around_match(line, pos)
            return truncated_line, line_index, 1.0

    tokens = re.split(r'\W', substr)
    tokens = [_.lower() for _ in tokens]

    candidates = []
    for line_index, line in enumerate(lines):
        _line = line.lower()
        score = 0
        first_match_pos = -1
        for token in tokens:
            token_pos = _line.find(token)
            if token_pos > -1:
                score += 1
                if first_match_pos == -1:
                    first_match_pos = token_pos

        if score > 0:
            truncated_line = _truncate_line_around_match(line, first_match_pos)
            candidates.append((truncated_line, line_index, score/len(tokens)))

    if not candidates:
        return '', -1, 0.0

    candidates = sorted(candidates, key=lambda item: -item[2])
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

    def search(self, project_path: str, needle: str, extension: str) -> tuple[int, list[dict]]:
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

            line, line_number, score = _find_subtext(lines, needle)
            if line and score > 0.0:
                results.append({
                    'file': file_path_relative,
                    'line_number': line_number,
                    'found': line.strip(),
                    'score': score
                })

        results = sorted(results, key=lambda r: -r['score'])

        logger.info(f"[search] total found: {len(results)}; total time: {time.time() - _start_time}")
        return len(results), results[:MAX_RESULTS]