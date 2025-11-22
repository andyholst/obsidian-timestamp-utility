import pytest
import os
from src.config import (
    AgenticsConfig,
    LLMConfig,
    ConfigValidationError,
    get_config,
    init_config,
    LOGGER_LEVEL,
    INFO_AS_DEBUG
)


@pytest.fixture
def clean_config():
    """Fixture to reset global config before each test."""
    global _config
    from src.config import _config
    original = _config
    _config = None
    yield
    _config = original


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Fixture to mock environment variables."""
    env_vars = {
        'GITHUB_TOKEN': 'test_token',
        'OLLAMA_HOST': 'http://localhost:11434',
        'OLLAMA_REASONING_MODEL': 'qwen2.5:14b',
        'OLLAMA_CODE_MODEL': 'qwen2.5-coder:14b'
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield
    # Cleanup not needed as monkeypatch handles it


class TestLLMConfig:
    """Test LLMConfig dataclass."""

    def test_llm_config_creation_with_defaults(self):
        """Test LLMConfig creation with default parameters."""
        config = LLMConfig(model="test-model", base_url="http://test.com")
        assert config.model == "test-model"
        assert config.base_url == "http://test.com"
        assert config.temperature == 0.7
        assert config.top_p == 0.7
        assert config.top_k == 20
        assert config.min_p == 0.0
        assert config.presence_penalty == 1.5
        assert config.num_ctx == 32768
        assert config.num_predict == 32768

    def test_llm_config_creation_with_custom_params(self):
        """Test LLMConfig creation with custom parameters."""
        config = LLMConfig(
            model="custom-model",
            base_url="https://custom.com",
            temperature=0.5,
            top_p=0.9,
            top_k=50,
            min_p=0.1,
            presence_penalty=2.0,
            num_ctx=16384,
            num_predict=8192
        )
        assert config.model == "custom-model"
        assert config.base_url == "https://custom.com"
        assert config.temperature == 0.5
        assert config.top_p == 0.9
        assert config.top_k == 50
        assert config.min_p == 0.1
        assert config.presence_penalty == 2.0
        assert config.num_ctx == 16384
        assert config.num_predict == 8192


class TestAgenticsConfig:
    """Test AgenticsConfig Pydantic model."""

    def test_agentics_config_with_valid_env_vars(self, mock_env_vars):
        """Test AgenticsConfig creation with valid environment variables."""
        config = AgenticsConfig()
        assert config.github_token == "test_token"
        assert config.ollama_host == "http://localhost:11434"
        assert config.ollama_reasoning_model == "qwen2.5:14b"
        assert config.ollama_code_model == "qwen2.5-coder:14b"
        assert config.circuit_breaker_failure_threshold == 3
        assert config.circuit_breaker_recovery_timeout == 30
        assert config.github_circuit_breaker_failure_threshold == 5
        assert config.github_circuit_breaker_recovery_timeout == 60
        assert config.logger_level == LOGGER_LEVEL
        assert config.info_as_debug == INFO_AS_DEBUG

    def test_agentics_config_with_defaults(self, monkeypatch):
        """Test AgenticsConfig with default values when env vars not set."""
        # Clear env vars
        monkeypatch.delenv('GITHUB_TOKEN', raising=False)
        monkeypatch.delenv('OLLAMA_HOST', raising=False)
        monkeypatch.delenv('OLLAMA_REASONING_MODEL', raising=False)
        monkeypatch.delenv('OLLAMA_CODE_MODEL', raising=False)

        config = AgenticsConfig()
        assert config.github_token is None  # Will be validated
        assert config.ollama_host == "http://localhost:11434"
        assert config.ollama_reasoning_model == "qwen2.5:14b"
        assert config.ollama_code_model == "qwen2.5-coder:14b"

    def test_agentics_config_github_token_validation_error(self, monkeypatch):
        """Test ConfigValidationError for missing github_token."""
        monkeypatch.delenv('GITHUB_TOKEN', raising=False)
        with pytest.raises(ConfigValidationError, match="GITHUB_TOKEN environment variable is required"):
            init_config(None)

    def test_agentics_config_ollama_host_validation_error(self, monkeypatch):
        """Test ConfigValidationError for invalid ollama_host."""
        monkeypatch.setenv('GITHUB_TOKEN', 'test_token')
        monkeypatch.setenv('OLLAMA_HOST', 'invalid-host')
        with pytest.raises(ConfigValidationError, match="OLLAMA_HOST must be a valid HTTP/HTTPS URL"):
            AgenticsConfig()

    def test_agentics_config_valid_ollama_host_https(self, monkeypatch):
        """Test valid HTTPS ollama_host."""
        monkeypatch.setenv('GITHUB_TOKEN', 'test_token')
        monkeypatch.setenv('OLLAMA_HOST', 'https://custom-host:8080')
        config = AgenticsConfig()
        assert config.ollama_host == "https://custom-host:8080"

    def test_get_reasoning_llm_config(self, mock_env_vars):
        """Test get_reasoning_llm_config method."""
        config = AgenticsConfig()
        llm_config = config.get_reasoning_llm_config()
        assert isinstance(llm_config, LLMConfig)
        assert llm_config.model == "qwen2.5:14b"
        assert llm_config.base_url == "http://localhost:11434"
        assert llm_config.temperature == 0.7
        assert llm_config.num_ctx == 32768

    def test_get_code_llm_config(self, mock_env_vars):
        """Test get_code_llm_config method."""
        config = AgenticsConfig()
        llm_config = config.get_code_llm_config()
        assert isinstance(llm_config, LLMConfig)
        assert llm_config.model == "qwen2.5-coder:14b"
        assert llm_config.base_url == "http://localhost:11434"
        assert llm_config.temperature == 0.7
        assert llm_config.num_ctx == 32768


class TestGlobalConfig:
    """Test global configuration management."""

    def test_init_config_with_custom_config(self, clean_config, mock_env_vars):
        """Test init_config with custom AgenticsConfig."""
        custom_config = AgenticsConfig()
        result = init_config(custom_config)
        assert result is custom_config
        assert get_config() is custom_config

    def test_init_config_with_none(self, clean_config, mock_env_vars):
        """Test init_config with None (uses defaults)."""
        result = init_config(None)
        assert isinstance(result, AgenticsConfig)
        assert get_config() is result

    def test_get_config_uninitialized(self, clean_config):
        """Test get_config raises error when not initialized."""
        with pytest.raises(RuntimeError, match="Configuration not initialized"):
            get_config()


class TestConfigValidationError:
    """Test ConfigValidationError exception."""

    def test_config_validation_error_instantiation(self):
        """Test ConfigValidationError can be instantiated."""
        error = ConfigValidationError("Test message")
        assert str(error) == "Test message"