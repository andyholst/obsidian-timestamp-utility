import os
import logging
from typing import Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field, field_validator


# Set to True to log messages originally at INFO level as DEBUG level
INFO_AS_DEBUG = True
# Default logger level; can be set to logging.DEBUG for more verbosity
LOGGER_LEVEL = logging.INFO


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for LLM clients."""
    model: str
    base_url: str
    temperature: float = 0.7
    top_p: float = 0.7
    top_k: int = 20
    min_p: float = 0.0
    presence_penalty: float = 1.5
    num_ctx: int = 32768
    num_predict: int = 32768


class AgenticsConfig(BaseModel):
    """Centralized configuration for the agentics application."""

    # GitHub configuration
    github_token: Optional[str] = Field(default_factory=lambda: os.getenv('GITHUB_TOKEN'))

    # Ollama configuration
    ollama_host: str = Field(default_factory=lambda: os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
    ollama_reasoning_model: str = Field(default_factory=lambda: os.getenv('OLLAMA_REASONING_MODEL', 'qwen2.5:14b'))
    ollama_code_model: str = Field(default_factory=lambda: os.getenv('OLLAMA_CODE_MODEL', 'qwen2.5-coder:14b'))

    # Circuit breaker configuration
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_recovery_timeout: int = 30
    github_circuit_breaker_failure_threshold: int = 5
    github_circuit_breaker_recovery_timeout: int = 60

    # Logging configuration
    logger_level: int = LOGGER_LEVEL
    info_as_debug: bool = INFO_AS_DEBUG

    @field_validator('ollama_host')
    def validate_ollama_host(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ConfigValidationError("OLLAMA_HOST must be a valid HTTP/HTTPS URL")
        return v

    def get_reasoning_llm_config(self) -> LLMConfig:
        """Get configuration for reasoning LLM."""
        return LLMConfig(
            model=self.ollama_reasoning_model,
            base_url=self.ollama_host,
            temperature=0.7,
            top_p=0.7,
            top_k=20,
            min_p=0.0,
            presence_penalty=1.5,
            num_ctx=32768,
            num_predict=32768
        )

    def get_code_llm_config(self) -> LLMConfig:
        """Get configuration for code generation LLM."""
        return LLMConfig(
            model=self.ollama_code_model,
            base_url=self.ollama_host,
            temperature=0.7,
            top_p=0.7,
            top_k=20,
            min_p=0.0,
            presence_penalty=1.5,
            num_ctx=32768,
            num_predict=32768
        )


# Global config instance - will be initialized by the application
_config: Optional[AgenticsConfig] = None


def get_config() -> AgenticsConfig:
    """Get the global configuration instance."""
    if _config is None:
        raise RuntimeError("Configuration not initialized")
    return _config


def init_config(config: Optional[AgenticsConfig] = None) -> AgenticsConfig:
    """Initialize the global configuration."""
    global _config
    if config is None:
        config = AgenticsConfig()
    if config.github_token is None:
        raise ConfigValidationError("GITHUB_TOKEN environment variable is required")
    _config = config
    return _config
