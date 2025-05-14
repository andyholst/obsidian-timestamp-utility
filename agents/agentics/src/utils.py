import re
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def validate_github_url(url: str) -> bool:
    logger.info(f"Validating GitHub URL: {url}")
    pattern = r'^https://github\.com/[\w-]+/[\w-]+/issues/\d+$'
    result = bool(re.match(pattern, url))
    logger.info(f"URL validation result: {result}")
    return result

def remove_thinking_tags(text: str) -> str:
    """Remove <think>...</think> tags from the text, including nested content."""
    logger.info("Removing thinking tags from text")
    logger.info(f"Input text: {text}")
    cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    logger.info(f"Text after removing tags: {cleaned_text}")
    return cleaned_text
