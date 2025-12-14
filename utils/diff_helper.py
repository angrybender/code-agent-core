import re

class PatchError(Exception):
    pass

def apply_patch(source_code: str, str_find: str, str_replace: str) -> str:
    cnt = source_code.count(str_find)
    if cnt > 1:
        raise PatchError("`str_find` contains more than once time in `source_code`")

    if cnt == 1:
        return source_code.replace(str_find, str_replace)

    source_code = source_code.split("\n")
    hashed_source = [re.sub(r'[\s+]', '', line) for line in source_code]
    hashed_str_find = [re.sub(r'[\s+]', '', line) for line in str_find.split("\n")]

    cmp_hash_find = " ".join(hashed_str_find)
    start_line = -1
    for i, code_line in enumerate(hashed_source):
        if code_line != hashed_str_find[0]:
            continue

        cmp_hash_source = " ".join(hashed_source[i:i+len(hashed_str_find)])
        if cmp_hash_source == cmp_hash_find and start_line >= 0:
            raise PatchError("`str_find` contains more than once time in `source_code`")
        elif cmp_hash_source == cmp_hash_find:
            start_line = i

    if start_line < 0:
        raise PatchError("`str_find` not contains `source_code`")

    str_replace = str_replace.split("\n")
    for j in range(0, len(hashed_str_find)):
        if start_line + j >= len(source_code):
            source_code.append('')

        if j < len(str_replace):
            source_code[start_line + j] = str_replace[j]
        else:
            source_code[start_line + j] = None

    source_code = [_ for _ in source_code if _ is not None]
    return "\n".join(source_code)
