import re
import json
import logging
from datetime import datetime
from dataclasses import is_dataclass, asdict
from .config import INFO_AS_DEBUG
from .monitoring import structured_log

monitor = structured_log(__name__)

def validate_github_url(url: str) -> bool:
    monitor.info("github_url_validation_start", data={"url": url})
    pattern = r'^https://github\.com/[\w-]+/[\w-]+/issues/\d+$'
    result = bool(re.match(pattern, url))
    monitor.info("github_url_validation_result", data={"url": url, "result": result})
    return result

def remove_thinking_tags(text: str) -> str:
    """Remove <think>...</think> tags and markdown code blocks from the text, excluding language specifiers."""
    monitor.info("remove_thinking_tags_start", data={"input_length": len(text)})
    monitor.debug("remove_thinking_tags_input", data={"text": text})

    # Remove <think>...</think> tags, including nested content
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    # Remove markdown code blocks, capturing only content after optional language specifier and newline
    text = re.sub(r'```(\w+)?\n(.*?)```', r'\2', text, flags=re.DOTALL)

    cleaned_text = text.strip()
    monitor.info("remove_thinking_tags_complete", data={"output_length": len(cleaned_text)})
    return cleaned_text

def log_info(component, msg, extra_data=None):
    """Log a message at INFO or DEBUG level based on INFO_AS_DEBUG setting."""
    monitor = structured_log(component)
    data = {"message": msg}
    if extra_data:
        data["extra_data"] = extra_data
    if INFO_AS_DEBUG:
        monitor.debug("log_info", data=data)
    else:
        monitor.info("log_info", data=data)

def parse_json_response(response: str, required_keys=None, fallback_defaults=None):
    """Parse JSON from LLM response with robust error handling and validation.

    Args:
        response: Raw LLM response string
        required_keys: Set of keys that must be present in the parsed JSON
        fallback_defaults: Dict of default values for missing required keys

    Returns:
        Parsed and validated JSON object

    Raises:
        ValueError: If JSON cannot be parsed or validation fails
    """
    monitor.info("json_parsing_start", data={"response_length": len(response), "response_preview": response[:200]})

    # Clean the response first
    cleaned_response = remove_thinking_tags(response).strip()

    parsing_attempts = [
        ("direct_parse", lambda: json.loads(cleaned_response)),
        ("markdown_code_block", lambda: _extract_json_from_markdown(cleaned_response)),
        ("brace_extraction", lambda: _extract_json_by_braces(cleaned_response)),
        ("regex_extraction", lambda: _extract_json_by_regex(cleaned_response)),
    ]

    last_error = None
    for attempt_name, parse_func in parsing_attempts:
        try:
            monitor.debug("json_parsing_attempt", data={"method": attempt_name})
            result = parse_func()
            monitor.info("json_parsing_success", data={"method": attempt_name})

            # Validate required keys if specified
            if required_keys:
                result = _validate_and_fill_json(result, required_keys, fallback_defaults or {})
                monitor.info("json_validation_passed", data={"required_keys": list(required_keys)})

            return result
        except (json.JSONDecodeError, ValueError) as e:
            monitor.warning("json_parsing_attempt_failed", data={"method": attempt_name, "error": str(e)})
            last_error = e
            continue

    monitor.error("json_parsing_all_failed", data={"last_error": str(last_error)})
    raise ValueError(f"LLM did not return a valid JSON object after trying all parsing methods. Last error: {str(last_error)}")


def _extract_json_from_markdown(text: str):
    """Extract JSON from markdown code blocks."""
    # Look for JSON code blocks
    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    if json_match:
        return json.loads(json_match.group(1).strip())
    raise ValueError("No JSON code block found")


def _extract_json_by_braces(text: str):
    """Extract JSON by finding balanced braces."""
    start_idx = text.find('{')
    if start_idx == -1:
        raise ValueError("No opening brace found")

    brace_count = 0
    for i, char in enumerate(text[start_idx:], start_idx):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                json_str = text[start_idx:i+1]
                return json.loads(json_str)

    raise ValueError("Unbalanced braces")


def _extract_json_by_regex(text: str):
    """Extract JSON using regex pattern."""
    # More robust regex that handles nested objects
    json_match = re.search(r'\{(?:[^{}]|{(?:[^{}]|{[^{}]*})*})*\}', text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(0))
    raise ValueError("No valid JSON pattern found")


def _validate_and_fill_json(parsed_json: dict, required_keys: set, defaults: dict) -> dict:
    """Validate required keys are present and fill with defaults if missing."""
    if not isinstance(parsed_json, dict):
        raise ValueError("Parsed result must be a dictionary")

    missing_keys = required_keys - set(parsed_json.keys())
    if missing_keys:
        monitor.warning("json_missing_keys", data={"missing_keys": list(missing_keys)})
        for key in missing_keys:
            if key in defaults:
                parsed_json[key] = defaults[key]
                monitor.info("json_key_filled_with_default", data={"key": key, "default": defaults[key]})
            else:
                raise ValueError(f"Required key '{key}' is missing and no default provided")

    return parsed_json


class SafeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that can handle dataclasses and other non-serializable objects"""

    def default(self, obj):
        try:
            if is_dataclass(obj):
                return asdict(obj)
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif hasattr(obj, '__dict__'):
                return obj.__dict__
            elif isinstance(obj, (set, frozenset)):
                return list(obj)
            else:
                return super().default(obj)
        except (TypeError, AttributeError, NameError):
            # Fallback for any serialization issues
            return f"<non-serializable: {type(obj).__name__}>"


def safe_json_dumps(obj, indent=None, **kwargs):
    """Safely serialize objects to JSON, handling dataclasses and other complex types"""
    try:
        return json.dumps(obj, cls=SafeJSONEncoder, indent=indent, **kwargs)
    except (TypeError, ValueError) as e:
        # Fallback: convert to string representation
        monitor.warning("json_serialization_fallback", data={"error": str(e), "object_type": type(obj).__name__})
        return json.dumps({"error": "Object not serializable", "type": type(obj).__name__, "repr": repr(obj)}, indent=indent, **kwargs)