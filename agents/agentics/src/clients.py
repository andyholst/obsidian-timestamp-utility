import os
from .monitoring import structured_log
import logging
from github import Github, Auth
from langchain_ollama import OllamaLLM

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
llm_reasoning = OllamaLLM(
    model=OLLAMA_REASONING_MODEL,
    base_url=OLLAMA_HOST,
    temperature=0.7,  # Lowered to reduce hallucinations
    top_p=0.7,        # Adjusted for more focused output
    top_k=20,
    min_p=0,
    extra_params={
        "presence_penalty": 1.5,
        "num_ctx": 32768,
        "num_predict": 32768
    }
)
llm_code = OllamaLLM(
    model=OLLAMA_CODE_MODEL,
    base_url=OLLAMA_HOST,
    temperature=0.7,  # Lowered to reduce hallucinations
    top_p=0.7,        # Adjusted for more focused output
    top_k=20,
    min_p=0,
    extra_params={
        "presence_penalty": 1.5,
        "num_ctx": 32768,
        "num_predict": 32768
    }
)
monitor.info("Ollama LLM clients initialized successfully")