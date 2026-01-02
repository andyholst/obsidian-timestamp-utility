import os
import logging
import json
import sys
from typing import Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field, field_validator, model_validator


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

    @model_validator(mode='after')
    def validate_ollama_host(cls, model):
        if not model.ollama_host.startswith(('http://', 'https://')):
            raise ConfigValidationError("OLLAMA_HOST must be a valid HTTP/HTTPS URL")
        return model

    @field_validator('github_token')
    @classmethod
    def validate_github_token(cls, v: Optional[str]) -> str:
        if v is None or str(v).strip() == "":
            raise ValueError("GITHUB_TOKEN must be a non-empty string")
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
    logging.debug(f"init_config: github_token = {repr(config.github_token)}")
    if config.github_token is None or config.github_token == '':
        raise ConfigValidationError("GITHUB_TOKEN environment variable is required and cannot be empty")
    _config = config

    # Setup logging with the configured level
    setup_logging(level=config.logger_level, enable_json=True)

    return _config


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record):
        """Format log record as JSON."""
        # If the message is already JSON (from StructuredLogger), use it directly
        if isinstance(record.getMessage(), str) and record.getMessage().startswith('{'):
            try:
                # Parse and re-format to ensure consistent structure
                log_data = json.loads(record.getMessage())
                return json.dumps(log_data, separators=(',', ':'))
            except json.JSONDecodeError:
                pass

        # Fallback for regular log messages
        log_entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage()
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, separators=(',', ':'))


def setup_logging(level: int = logging.INFO, enable_json: bool = True) -> None:
    """Setup logging configuration for the application.

    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        enable_json: Whether to use JSON formatting for structured logs
    """
    # Clear existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set root logger level
    root_logger.setLevel(level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if enable_json:
        # Use JSON formatter for structured logging
        formatter = JSONFormatter()
    else:
        # Use simple formatter for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Ensure structured loggers work properly
    # The StructuredLogger will inherit this configuration
