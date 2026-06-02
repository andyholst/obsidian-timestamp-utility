import re
from .config import INFO_AS_DEBUG
from .monitoring import structured_log

monitor = structured_log(__name__)


def validate_github_url(url: str) -> bool:
    monitor.info("github_url_validation_start", data={"url": url})
    pattern = r"^https://github\.com/[\w-]+/[\w-]+/issues/\d+$"
    result = bool(re.match(pattern, url))
    monitor.info("github_url_validation_result", data={"url": url, "result": result})
    return result


def remove_thinking_tags(text: str) -> str:
    """Remove <think>...</think> tags and markdown code blocks from the text, excluding language specifiers."""
    text = getattr(text, "content", text)
    text = str(text)
    monitor.info("remove_thinking_tags_start", data={"input_length": len(text)})
    monitor.debug("remove_thinking_tags_input", data={"text": text})

    # Remove <think>...</think> tags, including nested content
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # Remove markdown code blocks, capturing only content after optional language specifier and newline
    text = re.sub(r"```(\w+)?\n(.*?)```", r"\2", text, flags=re.DOTALL)

    cleaned_text = text.strip()
    monitor.info(
        "remove_thinking_tags_complete", data={"output_length": len(cleaned_text)}
    )
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
