import os
import time
from .monitoring import structured_log
import logging
from github import Github, Auth
from langchain_openai import ChatOpenAI

# Environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LLAMA_HOST = os.getenv("LLAMA_HOST", os.getenv("LLAMA_HOST", "http://localhost:11434"))
LLAMA_REASONING_MODEL = os.getenv("LLAMA_REASONING_MODEL", os.getenv("LLAMA_REASONING_MODEL", "qwen3.6-35b-a3b"))
LLAMA_CODE_MODEL = os.getenv("LLAMA_CODE_MODEL", os.getenv("LLAMA_CODE_MODEL", "qwen3.6-35b-a3b"))

monitor = structured_log(__name__)

# GitHub client will be initialized lazily
_github = None

def get_github():
    """Lazy initialization of GitHub client."""
    global _github
    if _github is None:
        _github = Github(GITHUB_TOKEN)
    return _github

# LLM clients will be initialized lazily
_llm_reasoning = None
_llm_code = None


class TimedChatOpenAI(ChatOpenAI):
    """Wrapper for ChatOpenAI that adds timing logs"""

    def __init__(self, *args, model_name="", **kwargs):
        super().__init__(*args, **kwargs)
        # Store model_name in a way that doesn't conflict with Pydantic
        object.__setattr__(self, "_model_name", model_name)

    def invoke(self, *args, **kwargs):
        start_time = time.time()
        model_name = getattr(self, "_model_name", "unknown")
        monitor.info(
            f"Starting LLM call to {model_name}",
            extra={
                "event": "llm_call_start",
                "model": model_name,
                "component": "clients",
            },
        )
        try:
            result = super().invoke(*args, **kwargs)
            duration = time.time() - start_time
            monitor.info(
                ".2f",
                extra={
                    "event": "llm_call_complete",
                    "model": model_name,
                    "duration_seconds": duration,
                    "component": "clients",
                },
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            monitor.error(
                ".2f",
                extra={
                    "event": "llm_call_error",
                    "model": model_name,
                    "duration_seconds": duration,
                    "error": str(e),
                    "component": "clients",
                },
            )
            raise


def _create_llm(model, name):
    """Create an LLM client instance."""
    return TimedChatOpenAI(
        model=model,
        base_url=LLAMA_HOST,
        temperature=0.7,  # Lowered to reduce hallucinations
        top_p=0.7,  # Adjusted for more focused output
        top_k=20,
        min_p=0,
        model_name=name,
        extra_params={"presence_penalty": 1.5, "num_ctx": 32768, "num_predict": 32768},
    )


def get_llm_reasoning():
    """Lazy initialization of reasoning LLM."""
    global _llm_reasoning
    if _llm_reasoning is None:
        monitor.info("Initializing reasoning LLM")
        _llm_reasoning = _create_llm(LLAMA_REASONING_MODEL, "reasoning")
        monitor.info("Reasoning LLM initialized successfully")
    return _llm_reasoning


def get_llm_code():
    """Lazy initialization of code LLM."""
    global _llm_code
    if _llm_code is None:
        monitor.info("Initializing code LLM")
        _llm_code = _create_llm(LLAMA_CODE_MODEL, "code")
        monitor.info("Code LLM initialized successfully")
    return _llm_code


# For backward compatibility - these will be None until accessed
llm_reasoning = None
llm_code = None
