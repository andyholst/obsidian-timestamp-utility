import os
import time
from .monitoring import structured_log
import logging
from github import Github, Auth
from langchain_ollama import ChatOllama

# Environment variables
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_REASONING_MODEL = os.getenv('OLLAMA_REASONING_MODEL', 'qwen2.5:14b')
OLLAMA_CODE_MODEL = os.getenv('OLLAMA_CODE_MODEL', 'qwen2.5-coder:14b')

monitor = structured_log(__name__)

# GitHub client will be initialized lazily
github = None

# Initialize Ollama LLM clients
monitor.info("Initializing Ollama LLM clients")

class TimedOllamaLLM(ChatOllama):
    """Wrapper for OllamaLLM that adds timing logs"""

    def __init__(self, *args, model_name="", **kwargs):
        super().__init__(*args, **kwargs)
        # Store model_name in a way that doesn't conflict with Pydantic
        object.__setattr__(self, '_model_name', model_name)

    def invoke(self, *args, **kwargs):
        start_time = time.time()
        model_name = getattr(self, '_model_name', 'unknown')
        monitor.info(f"Starting LLM call to {model_name}", extra={
            "event": "llm_call_start",
            "model": model_name,
            "component": "clients"
        })
        try:
            result = super().invoke(*args, **kwargs)
            duration = time.time() - start_time
            monitor.info(".2f", extra={
                "event": "llm_call_complete",
                "model": model_name,
                "duration_seconds": duration,
                "component": "clients"
            })
            return result
        except Exception as e:
            duration = time.time() - start_time
            monitor.error(".2f", extra={
                "event": "llm_call_error",
                "model": model_name,
                "duration_seconds": duration,
                "error": str(e),
                "component": "clients"
            })
            raise

llm_reasoning = TimedOllamaLLM(
    model=OLLAMA_REASONING_MODEL,
    base_url=OLLAMA_HOST,
    temperature=0.7,  # Lowered to reduce hallucinations
    top_p=0.7,        # Adjusted for more focused output
    top_k=20,
    min_p=0,
    model_name="reasoning",
    extra_params={
        "presence_penalty": 1.5,
        "num_ctx": 32768,
        "num_predict": 32768
    }
)
llm_code = TimedOllamaLLM(
    model=OLLAMA_CODE_MODEL,
    base_url=OLLAMA_HOST,
    temperature=0.7,  # Lowered to reduce hallucinations
    top_p=0.7,        # Adjusted for more focused output
    top_k=20,
    min_p=0,
    model_name="code",
    extra_params={
        "presence_penalty": 1.5,
        "num_ctx": 32768,
        "num_predict": 32768
    }
)
monitor.info("Ollama LLM clients initialized successfully")