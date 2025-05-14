import re
import logging
from .config import INFO_AS_DEBUG

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def validate_github_url(url: str) -> bool:
    logger.info(f"Validating GitHub URL: {url}")
    pattern = r'^https://github\.com/[\w-]+/[\w-]+/issues/\d+$'
    result = bool(re.match(pattern, url))
    logger.info(f"URL validation result: {result}")
    return result

def remove_thinking_tags(text: str) -> str:
    """Remove <think>...</think> tags and markdown code blocks from the text, excluding language specifiers."""
    logger.info("Removing thinking tags and markdown code blocks from text")
    logger.info(f"Input text: {text}")
    
    # Remove <think>...</think> tags, including nested content
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # Remove markdown code blocks, capturing only content after optional language specifier and newline
    text = re.sub(r'```(\w+)?\n(.*?)```', r'\2', text, flags=re.DOTALL)
    
    cleaned_text = text.strip()
    logger.info(f"Text after removing tags and code blocks: {cleaned_text}")
    return cleaned_text

def log_info(logger, msg):
    """Log a message at INFO or DEBUG level based on INFO_AS_DEBUG setting."""
    if INFO_AS_DEBUG:
        logger.debug(msg)
    else:
        logger.info(msg)
