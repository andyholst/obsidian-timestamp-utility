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

def parse_json_response(response: str):
    """Parse JSON from LLM response, handling extra text after JSON."""
    import json
    logger.info(f"Parsing JSON response: {response}")
    try:
        result = json.loads(response.strip())
        logger.info(f"Parsed JSON directly: {result}")
        return result
    except json.JSONDecodeError as e:
        logger.warning(f"JSONDecodeError: {str(e)}")
        # Try to extract JSON from the response by finding the first valid JSON object
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                logger.info(f"Recovered JSON from regex: {result}")
                return result
            except json.JSONDecodeError:
                pass
        # If regex fails, try to clean the response further
        # Remove any extra text after the JSON
        json_start = response.find('{')
        if json_start != -1:
            json_content = response[json_start:]
            # Find the end of the JSON object by counting braces
            brace_count = 0
            end_pos = 0
            for i, char in enumerate(json_content):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            if brace_count == 0 and end_pos > 0:
                try:
                    result = json.loads(json_content[:end_pos])
                    logger.info(f"Recovered JSON by brace counting: {result}")
                    return result
                except json.JSONDecodeError:
                    pass
        logger.error("Failed to parse JSON from response")
        raise ValueError("LLM did not return a valid JSON object")
