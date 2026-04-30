import glob
import os
import re

import frontmatter


_CODE_BLOCK_RE = re.compile(r"```(?:[^\n`]*)\n(.*?)```", re.DOTALL)



def parse_mcp_commands(commands_dir: str) -> list:
    if not os.path.isdir(commands_dir):
        return []

    commands = []
    for path in sorted(glob.glob(os.path.join(commands_dir, '*.md'))):
        with open(path, 'r', encoding='utf-8') as f:
            post = frontmatter.loads(f.read())

        metadata = dict(post.metadata or {})
        if metadata.get('mcp') is not True:
            continue
        if metadata.get('enabled') is False:
            continue

        body = post.content or ''
        match = _CODE_BLOCK_RE.search(body)
        if not match:
            continue

        cmd = match.group(1).strip()
        if not cmd:
            continue

        description = _CODE_BLOCK_RE.sub('', body, count=1).strip()
        config = dict(metadata)
        config.pop('mcp', None)
        config.pop('enabled', None)

        commands.append({
            'command': os.path.splitext(os.path.basename(path))[0],
            'description': description,
            'cmd': cmd,
            'config': config,
        })

    return commands