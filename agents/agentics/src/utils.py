# utils.py
import re
import logging
from .config import INFO_AS_DEBUG

def validate_github_url(url: str) -> bool:
    pattern = r'^https://github\.com/[\w-]+/[\w-]+/issues/\d+$'
    return bool(re.match(pattern, url))

def remove_thinking_tags(text: str) -> str:
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'```(\w+)?\n(.*?)```', r'\2', text, flags=re.DOTALL)
    return text.strip()

def log_info(logger, msg):
    if INFO_AS_DEBUG:
        logger.debug(msg)
    else:
        logger.info(msg)
