import re

def validate_github_url(url: str) -> bool:
    pattern = r'^https://github\.com/[\w-]+/[\w-]+/issues/\d+$'
    return bool(re.match(pattern, url))
