import os
import time
from .monitoring import structured_log
import logging
from github import Github, Auth
from langchain_openai import OpenAI

# Environment variables (kept as OLLAMA_* for compatibility with llama.cpp server on port 11434)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "qwen3.6-35b-a3b")
OLLAMA_CODE_MODEL = os.getenv("OLLAMA_CODE_MODEL", "qwen3.6-35b-a3b")

monitor = structured_log(__name__)

# GitHub client will be initialized lazily
github = None

# Initialize LLM clients (OpenAI-compatible for llama.cpp)
monitor.info("Initializing LLM clients (OpenAI-compatible)")


def _ensure_v1(url: str) -> str:
    """Ensure the URL ends with /v1 for OpenAI-compatible endpoints."""
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    return url


class TimedOpenAI(OpenAI):
    """Wrapper for OpenAI that adds timing logs."""

    def __init__(self, *args, model_name="", **kwargs):
        super().__init__(*args, **kwargs)
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


llm_reasoning = TimedOpenAI(
    model=OLLAMA_REASONING_MODEL,
    base_url=_ensure_v1(OLLAMA_HOST),
    temperature=0.7,
    top_p=0.7,
    api_key="not-needed",
    model_name="reasoning",
)
llm_code = TimedOpenAI(
    model=OLLAMA_CODE_MODEL,
    base_url=_ensure_v1(OLLAMA_HOST),
    temperature=0.7,
    top_p=0.7,
    api_key="not-needed",
    model_name="code",
)
monitor.info("LLM clients initialized successfully (OpenAI-compatible)")
