import os
import time
from .monitoring import structured_log
import logging
from github import Github, Auth
from langchain_ollama import OllamaLLM

# Environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LLAMA_HOST = os.getenv("LLAMA_HOST", "http://localhost:11434")
LLAMA_REASONING_MODEL = os.getenv("LLAMA_REASONING_MODEL", "sorc/qwen3.5-claude-4.6-opus:9b")
LLAMA_CODE_MODEL = os.getenv("LLAMA_CODE_MODEL", "sorc/qwen3.5-claude-4.6-opus:9b")

monitor = structured_log(__name__)

# GitHub client will be initialized lazily
github = None

# Initialize llama LLM clients
monitor.info("Initializing llama LLM clients")


class TimedOllamaLLM(OllamaLLM):
    """Wrapper for OllamaLLM that adds timing logs"""

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


llm_reasoning = TimedOllamaLLM(
    model=LLAMA_REASONING_MODEL,
    base_url=LLAMA_HOST,
    temperature=0.7,  # Lowered to reduce hallucinations
    top_p=0.7,  # Adjusted for more focused output
    top_k=20,
    min_p=0,
    model_name="reasoning",
    extra_params={"presence_penalty": 1.5, "num_ctx": 32768, "num_predict": 32768},
)
llm_code = TimedOllamaLLM(
    model=LLAMA_CODE_MODEL,
    base_url=LLAMA_HOST,
    temperature=0.7,  # Lowered to reduce hallucinations
    top_p=0.7,  # Adjusted for more focused output
    top_k=20,
    min_p=0,
    model_name="code",
    extra_params={"presence_penalty": 1.5, "num_ctx": 32768, "num_predict": 32768},
)
monitor.info("llama LLM clients initialized successfully")
