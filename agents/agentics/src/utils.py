import re
import json

def validate_github_url(url: str) -> bool:
    pattern = r'^https://github\.com/[\w-]+/[\w-]+/issues/\d+$'
    return bool(re.match(pattern, url))

def validate_llm_response(response: dict) -> bool:
    required_keys = {'title', 'description', 'requirements', 'acceptance_criteria'}
    if not required_keys.issubset(response.keys()):
        return False
    if not isinstance(response['requirements'], list) or not isinstance(response['acceptance_criteria'], list):
        return False
    return True
