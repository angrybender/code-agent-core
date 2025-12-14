import re

def parse_tags(content: str, tags: list, support_tag_attr=False) -> dict:
    output = {}
    for tag in tags:
        pattern1 = rf'<{tag}>(.*?)</{tag}>'
        pattern2 = rf'<{tag} [a-z]+=[^>]+>(.*?)</{tag}>'

        # Search for the pattern in the provided text
        match = re.findall(pattern1, content, re.DOTALL)
        match_with_attrs = re.findall(pattern2, content, re.DOTALL)

        # If a match is found, return the content; otherwise, return None
        if match:
            output[tag] = match
        elif match_with_attrs:
            output[tag] = match_with_attrs

    return output