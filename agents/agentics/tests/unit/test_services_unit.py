import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from src.services import (
    ServiceClient,
    OllamaClient,
    GitHubClient,
    MCPClient,
    ServiceManager,
    get_service_manager,
    init_services,
    _service_manager
)
from src.exceptions import OllamaError, GitHubError, MCPError, ServiceUnavailableError
from src.config import LLMConfig
from src.circuit_breaker import CircuitBreaker, ServiceHealthMonitor
from tests.fixtures.mock_circuit_breaker import create_mock_circuit_breaker, patch_circuit_breakers
from tests.fixtures.mock_llm_responses import create_mock_llm_response
from tests.fixtures.mock_github_responses import create_github_client_mock


class ConcreteServiceClient(ServiceClient):
    """Concrete test implementation of ServiceClient."""

    async def health_check(self) -> bool:
        return True

    def is_available(self) -> bool:
        return True


@pytest.fixture
def mock_health_monitor():
    """Mock health monitor."""
    monitor = MagicMock(spec=ServiceHealthMonitor)
    monitor.is_service_healthy.return_value = True
    monitor.register_service = MagicMock()
    return monitor


@pytest.fixture
def mock_circuit_breaker():
    """Mock circuit breaker."""
    cb = MagicMock(spec=CircuitBreaker)

    def mock_call(func):
        """Mock circuit breaker call that returns a wrapper."""
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper

    cb.call.side_effect = mock_call
    cb.state = "closed"
    cb.failure_count = 0
    return cb


@pytest.fixture
def mock_llm_config():
    """Mock LLM configuration."""
    return LLMConfig(
        model="test-model",
        base_url="http://test.com",
        temperature=0.7,
        top_p=0.9,
        top_k=40,
        min_p=0.0,
        presence_penalty=1.0,
        num_ctx=4096,
        num_predict=2048
    )


@pytest.fixture
def mock_github_token():
    """Mock GitHub token."""
    return "test_github_token"


@pytest.fixture
def mock_mcp_client():
    """Mock MCP client."""
    client = MagicMock()
    client.get_context.return_value = "mock context"
    client.store_memory.return_value = None
    client.retrieve_memory.return_value = "mock memory"
    return client


class TestServiceClientTests:
    """Test ServiceClient base class functionality."""

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    def test_service_client_initialization(self, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test ServiceClient initialization."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = ConcreteServiceClient("test_service")

        assert client.name == "test_service"
        assert client.circuit_breaker == mock_circuit_breaker
        assert client.health_monitor == mock_health_monitor

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    def test_service_client_abstract_methods(self, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test that ServiceClient abstract methods raise NotImplementedError."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = ConcreteServiceClient("test_service")

        # These should work since we implemented them
        assert asyncio.run(client.health_check()) is True
        assert client.is_available() is True


class TestOllamaClient:
    """Test OllamaClient functionality."""

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaLLM')
    def test_ollama_client_initialization_success(self, mock_ollama_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_llm_config, mock_circuit_breaker, mock_health_monitor):
        """Test OllamaClient initialization with valid config."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_llm_instance = MagicMock()
        mock_ollama_class.return_value = mock_llm_instance

        client = OllamaClient(mock_llm_config)

        assert client.config == mock_llm_config
        assert client._client == mock_llm_instance
        mock_ollama_class.assert_called_once_with(
            model="test-model",
            base_url="http://test.com",
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            min_p=0.0,
            extra_params={
                "presence_penalty": 1.0,
                "num_ctx": 4096,
                "num_predict": 2048
            }
        )

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaLLM')
    def test_ollama_client_initialization_failure(self, mock_ollama_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_llm_config, mock_circuit_breaker, mock_health_monitor):
        """Test OllamaClient initialization failure."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_ollama_class.side_effect = Exception("Init failed")

        client = OllamaClient(mock_llm_config)

        assert client._client is None

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaLLM')
    def test_ollama_client_health_check_success(self, mock_ollama_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_llm_config, mock_circuit_breaker, mock_health_monitor):
        """Test OllamaClient health check success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = "Hello response"
        mock_ollama_class.return_value = mock_llm_instance

        client = OllamaClient(mock_llm_config)

        # Mock asyncio loop
        async def mock_run_in_executor(*args, **kwargs):
            return "Hello response"

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = mock_run_in_executor

            result = asyncio.run(client.health_check())

            assert result is True

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaLLM')
    def test_ollama_client_health_check_no_client(self, mock_ollama_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_llm_config, mock_circuit_breaker, mock_health_monitor):
        """Test OllamaClient health check when client is None."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_ollama_class.side_effect = Exception("Init failed")

        client = OllamaClient(mock_llm_config)

        result = asyncio.run(client.health_check())

        assert result is False

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaLLM')
    def test_ollama_client_health_check_exception(self, mock_ollama_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_llm_config, mock_circuit_breaker, mock_health_monitor):
        """Test OllamaClient health check with exception."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_llm_instance = MagicMock()
        mock_ollama_class.return_value = mock_llm_instance

        client = OllamaClient(mock_llm_config)

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor.side_effect = Exception("Health check failed")

            result = asyncio.run(client.health_check())

            assert result is False

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaLLM')
    def test_ollama_client_is_available(self, mock_ollama_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_llm_config, mock_circuit_breaker, mock_health_monitor):
        """Test OllamaClient is_available method."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_llm_instance = MagicMock()
        mock_ollama_class.return_value = mock_llm_instance

        client = OllamaClient(mock_llm_config)

        result = client.is_available()

        assert result is True
        mock_health_monitor.is_service_healthy.assert_called_once_with("ollama")

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaLLM')
    def test_ollama_client_is_available_no_client(self, mock_ollama_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_llm_config, mock_circuit_breaker, mock_health_monitor):
        """Test OllamaClient is_available when client is None."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_ollama_class.side_effect = Exception("Init failed")

        client = OllamaClient(mock_llm_config)

        result = client.is_available()

        assert result is False

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaLLM')
    def test_ollama_client_invoke_success(self, mock_ollama_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_llm_config, mock_circuit_breaker, mock_health_monitor):
        """Test OllamaClient invoke method success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = "LLM response"
        mock_ollama_class.return_value = mock_llm_instance

        client = OllamaClient(mock_llm_config)

        result = client.invoke("Test prompt")

        assert result == "LLM response"
        mock_llm_instance.invoke.assert_called_once_with("Test prompt")

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaLLM')
    def test_ollama_client_invoke_not_available(self, mock_ollama_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_llm_config, mock_circuit_breaker, mock_health_monitor):
        """Test OllamaClient invoke when service not available."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor
        mock_health_monitor.is_service_healthy.return_value = False

        mock_llm_instance = MagicMock()
        mock_ollama_class.return_value = mock_llm_instance

        client = OllamaClient(mock_llm_config)

        with pytest.raises(OllamaError, match="Ollama service \\(test-model\\) is not available"):
            client.invoke("Test prompt")


class TestGitHubClient:
    """Test GitHubClient functionality."""

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.Github')
    @patch('src.services.Auth')
    def test_github_client_initialization_success(self, mock_auth_class, mock_github_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_github_token, mock_circuit_breaker, mock_health_monitor):
        """Test GitHubClient initialization with valid token."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_auth_instance = MagicMock()
        mock_auth_class.Token.return_value = mock_auth_instance

        mock_github_instance = MagicMock()
        mock_github_class.return_value = mock_github_instance

        client = GitHubClient(mock_github_token)

        assert client.token == mock_github_token
        assert client._client == mock_github_instance
        mock_auth_class.Token.assert_called_once_with(mock_github_token)
        mock_github_class.assert_called_once_with(auth=mock_auth_instance)

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.Github')
    @patch('src.services.Auth')
    def test_github_client_initialization_failure(self, mock_auth_class, mock_github_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_github_token, mock_circuit_breaker, mock_health_monitor):
        """Test GitHubClient initialization failure."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_github_class.side_effect = Exception("Init failed")

        client = GitHubClient(mock_github_token)

        assert client._client is None

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.Github')
    @patch('src.services.Auth')
    def test_github_client_health_check_success(self, mock_auth_class, mock_github_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_github_token, mock_circuit_breaker, mock_health_monitor):
        """Test GitHubClient health check success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_github_instance = MagicMock()
        mock_user = MagicMock()
        mock_user.login = "testuser"
        mock_github_instance.get_user.return_value = mock_user
        mock_github_class.return_value = mock_github_instance

        client = GitHubClient(mock_github_token)

        async def mock_run_in_executor(*args, **kwargs):
            return mock_user

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = mock_run_in_executor

            result = asyncio.run(client.health_check())

            assert result is True

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.Github')
    @patch('src.services.Auth')
    def test_github_client_health_check_no_client(self, mock_auth_class, mock_github_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_github_token, mock_circuit_breaker, mock_health_monitor):
        """Test GitHubClient health check when client is None."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_github_class.side_effect = Exception("Init failed")

        client = GitHubClient(mock_github_token)

        result = asyncio.run(client.health_check())

        assert result is False

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.Github')
    @patch('src.services.Auth')
    def test_github_client_is_available(self, mock_auth_class, mock_github_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_github_token, mock_circuit_breaker, mock_health_monitor):
        """Test GitHubClient is_available method."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_github_instance = MagicMock()
        mock_github_class.return_value = mock_github_instance

        client = GitHubClient(mock_github_token)

        result = client.is_available()

        assert result is True
        mock_health_monitor.is_service_healthy.assert_called_once_with("github")

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.Github')
    @patch('src.services.Auth')
    def test_github_client_is_available_no_client(self, mock_auth_class, mock_github_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_github_token, mock_circuit_breaker, mock_health_monitor):
        """Test GitHubClient is_available when client is None."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_github_class.side_effect = Exception("Init failed")

        client = GitHubClient(mock_github_token)

        result = client.is_available()

        assert result is False

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.Github')
    @patch('src.services.Auth')
    def test_github_client_get_user_success(self, mock_auth_class, mock_github_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_github_token, mock_circuit_breaker, mock_health_monitor):
        """Test GitHubClient get_user method success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_github_instance = MagicMock()
        mock_user = MagicMock()
        mock_github_instance.get_user.return_value = mock_user
        mock_github_class.return_value = mock_github_instance

        client = GitHubClient(mock_github_token)

        result = client.get_user()

        assert result == mock_user
        mock_github_instance.get_user.assert_called_once()

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.Github')
    @patch('src.services.Auth')
    def test_github_client_get_user_not_available(self, mock_auth_class, mock_github_class, mock_get_health_monitor, mock_get_circuit_breaker, mock_github_token, mock_circuit_breaker, mock_health_monitor):
        """Test GitHubClient get_user when service not available."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor
        mock_health_monitor.is_service_healthy.return_value = False

        mock_github_instance = MagicMock()
        mock_github_class.return_value = mock_github_instance

        client = GitHubClient(mock_github_token)

        with pytest.raises(GitHubError, match="GitHub service is not available"):
            client.get_user()


class TestMCPClient:
    """Test MCPClient functionality."""

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    def test_mcp_client_initialization(self, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test MCPClient initialization."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = MCPClient()

        assert client.name == "mcp"
        assert client._initialized is False
        assert client._tools == []

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.init_mcp_client')
    def test_mcp_client_initialize_success(self, mock_init_mcp, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test MCPClient initialize success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_init_mcp.return_value = MagicMock()

        client = MCPClient()

        asyncio.run(client.initialize())

        assert client._initialized is True
        mock_init_mcp.assert_called_once()

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.init_mcp_client')
    def test_mcp_client_initialize_failure(self, mock_init_mcp, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test MCPClient initialize failure."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_init_mcp.side_effect = Exception("Init failed")

        client = MCPClient()

        asyncio.run(client.initialize())

        assert client._initialized is False

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.get_mcp_client')
    def test_mcp_client_health_check_success(self, mock_get_mcp, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor, mock_mcp_client):
        """Test MCPClient health check success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor
        mock_get_mcp.return_value = mock_mcp_client

        client = MCPClient()
        client._initialized = True

        result = asyncio.run(client.health_check())

        assert result is True
        mock_get_mcp.assert_called_once()

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    def test_mcp_client_health_check_not_initialized(self, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test MCPClient health check when not initialized."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = MCPClient()

        result = asyncio.run(client.health_check())

        assert result is False

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    def test_mcp_client_is_available(self, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test MCPClient is_available method."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = MCPClient()
        client._initialized = True

        result = client.is_available()

        assert result is True
        mock_health_monitor.is_service_healthy.assert_called_once_with("mcp")

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    def test_mcp_client_is_available_not_initialized(self, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test MCPClient is_available when not initialized."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = MCPClient()

        result = client.is_available()

        assert result is False

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.get_mcp_client')
    def test_mcp_client_get_context_success(self, mock_get_mcp, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor, mock_mcp_client):
        """Test MCPClient get_context success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor
        mock_get_mcp.return_value = mock_mcp_client

        client = MCPClient()
        client._initialized = True

        result = asyncio.run(client.get_context("test query", 4096))

        assert result == "mock context"
        mock_mcp_client.get_context.assert_called_once_with("test query", 4096)

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    def test_mcp_client_get_context_not_available(self, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test MCPClient get_context when service not available."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor
        mock_health_monitor.is_service_healthy.return_value = False

        client = MCPClient()
        client._initialized = True

        with pytest.raises(MCPError, match="MCP service is not available"):
            asyncio.run(client.get_context("test query"))

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.get_mcp_client')
    def test_mcp_client_store_memory_success(self, mock_get_mcp, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor, mock_mcp_client):
        """Test MCPClient store_memory success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor
        mock_get_mcp.return_value = mock_mcp_client

        client = MCPClient()
        client._initialized = True

        asyncio.run(client.store_memory("key", "value"))

        mock_mcp_client.store_memory.assert_called_once_with("key", "value")

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.get_mcp_client')
    def test_mcp_client_retrieve_memory_success(self, mock_get_mcp, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor, mock_mcp_client):
        """Test MCPClient retrieve_memory success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor
        mock_get_mcp.return_value = mock_mcp_client

        client = MCPClient()
        client._initialized = True

        result = asyncio.run(client.retrieve_memory("key"))

        assert result == "mock memory"
        mock_mcp_client.retrieve_memory.assert_called_once_with("key")

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.get_mcp_client')
    @patch('src.services.Tool')
    def test_mcp_client_get_tools(self, mock_tool_class, mock_get_mcp, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor, mock_mcp_client):
        """Test MCPClient get_tools method."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor
        mock_get_mcp.return_value = mock_mcp_client

        mock_tool1 = MagicMock()
        mock_tool2 = MagicMock()
        mock_tool3 = MagicMock()
        mock_tool_class.from_function.side_effect = [mock_tool1, mock_tool2, mock_tool3]

        client = MCPClient()
        client._initialized = True

        tools = client.get_tools()

        assert len(tools) == 3
        assert tools == [mock_tool1, mock_tool2, mock_tool3]
        assert client._tools == [mock_tool1, mock_tool2, mock_tool3]

        # Call again to test caching
        tools2 = client.get_tools()
        assert tools2 == [mock_tool1, mock_tool2, mock_tool3]
        # Should not create new tools
        assert mock_tool_class.from_function.call_count == 3

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    def test_mcp_client_get_tools_not_available(self, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test MCPClient get_tools when service not available."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = MCPClient()

        tools = client.get_tools()

        assert tools == []

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.close_mcp_client')
    def test_mcp_client_close_success(self, mock_close_mcp, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test MCPClient close success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_close_mcp.return_value = MagicMock()

        client = MCPClient()
        client._initialized = True

        asyncio.run(client.close())

        assert client._initialized is False
        mock_close_mcp.assert_called_once()

    @patch('src.services.get_circuit_breaker')
    @patch('src.services.get_health_monitor')
    @patch('src.services.close_mcp_client')
    def test_mcp_client_close_failure(self, mock_close_mcp, mock_get_health_monitor, mock_get_circuit_breaker, mock_circuit_breaker, mock_health_monitor):
        """Test MCPClient close failure."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_close_mcp.side_effect = Exception("Close failed")

        client = MCPClient()
        client._initialized = True

        asyncio.run(client.close())

        assert client._initialized is False


class TestServiceManager:
    """Test ServiceManager functionality."""

    @patch('src.services.get_health_monitor')
    def test_service_manager_initialization(self, mock_get_health_monitor, mock_health_monitor):
        """Test ServiceManager initialization."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        manager = ServiceManager(config)

        assert manager.config == config
        assert manager.ollama_reasoning is None
        assert manager.ollama_code is None
        assert manager.github is None
        assert manager.mcp is None
        assert manager.health_monitor == mock_health_monitor

    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaClient')
    @patch('src.services.GitHubClient')
    @patch('src.services.MCPClient')
    def test_service_manager_initialize_services(self, mock_mcp_class, mock_github_class, mock_ollama_class, mock_get_health_monitor, mock_health_monitor, mock_llm_config):
        """Test ServiceManager initialize_services."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        config.get_reasoning_llm_config.return_value = mock_llm_config
        config.get_code_llm_config.return_value = mock_llm_config
        config.github_token = "test_token"

        mock_ollama_reasoning = MagicMock()
        mock_ollama_code = MagicMock()
        mock_github = MagicMock()
        mock_mcp = MagicMock()

        mock_ollama_class.side_effect = [mock_ollama_reasoning, mock_ollama_code]
        mock_github_class.return_value = mock_github
        mock_mcp_class.return_value = mock_mcp

        manager = ServiceManager(config)

        asyncio.run(manager.initialize_services())

        assert manager.ollama_reasoning == mock_ollama_reasoning
        assert manager.ollama_code == mock_ollama_code
        assert manager.github == mock_github
        assert manager.mcp == mock_mcp

        mock_health_monitor.register_service.assert_any_call("ollama_reasoning", mock_ollama_reasoning.health_check)
        mock_health_monitor.register_service.assert_any_call("ollama_code", mock_ollama_code.health_check)
        mock_health_monitor.register_service.assert_any_call("github", mock_github.health_check)
        mock_health_monitor.register_service.assert_any_call("mcp", mock_mcp.health_check)

    @patch('src.services.get_health_monitor')
    @patch('src.services.OllamaClient')
    @patch('src.services.GitHubClient')
    @patch('src.services.MCPClient')
    def test_service_manager_initialize_services_no_github_token(self, mock_mcp_class, mock_github_class, mock_ollama_class, mock_get_health_monitor, mock_health_monitor, mock_llm_config):
        """Test ServiceManager initialize_services without GitHub token."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        config.get_reasoning_llm_config.return_value = mock_llm_config
        config.get_code_llm_config.return_value = mock_llm_config
        config.github_token = None

        mock_ollama_reasoning = MagicMock()
        mock_ollama_code = MagicMock()
        mock_mcp = MagicMock()

        mock_ollama_class.side_effect = [mock_ollama_reasoning, mock_ollama_code]
        mock_mcp_class.return_value = mock_mcp

        manager = ServiceManager(config)

        asyncio.run(manager.initialize_services())

        assert manager.github is None
        mock_github_class.assert_not_called()

    @patch('src.services.get_health_monitor')
    def test_service_manager_check_services_health(self, mock_get_health_monitor, mock_health_monitor):
        """Test ServiceManager check_services_health."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        manager = ServiceManager(config)

        # Mock services
        mock_ollama_reasoning = MagicMock()
        mock_ollama_reasoning.health_check = AsyncMock(return_value=True)
        mock_ollama_code = MagicMock()
        mock_ollama_code.health_check = AsyncMock(return_value=False)
        mock_github = MagicMock()
        mock_github.health_check = AsyncMock(return_value=True)
        mock_mcp = MagicMock()
        mock_mcp.health_check = AsyncMock(return_value=True)

        manager.ollama_reasoning = mock_ollama_reasoning
        manager.ollama_code = mock_ollama_code
        manager.github = mock_github
        manager.mcp = mock_mcp

        result = asyncio.run(manager.check_services_health())

        expected = {
            "ollama_reasoning": True,
            "ollama_code": False,
            "github": True,
            "mcp": True
        }
        assert result == expected

    @patch('src.services.get_health_monitor')
    def test_service_manager_check_services_health_none_services(self, mock_get_health_monitor, mock_health_monitor):
        """Test ServiceManager check_services_health with None services."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        manager = ServiceManager(config)

        # Ensure services are None
        manager.ollama_reasoning = None
        manager.ollama_code = None
        manager.github = None
        manager.mcp = None

        result = asyncio.run(manager.check_services_health())

        expected = {
            "ollama_reasoning": False,
            "ollama_code": False,
            "github": False,
            "mcp": False
        }
        assert result == expected

    @patch('src.services.get_health_monitor')
    def test_service_manager_close_services(self, mock_get_health_monitor, mock_health_monitor):
        """Test ServiceManager close_services."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        manager = ServiceManager(config)

        mock_mcp = MagicMock()
        mock_mcp.close = AsyncMock()
        manager.mcp = mock_mcp

        asyncio.run(manager.close_services())

        mock_mcp.close.assert_called_once()


class TestGlobalServiceFunctions:
    """Test global service management functions."""

    @patch('src.services._service_manager', None)
    def test_get_service_manager_not_initialized(self):
        """Test get_service_manager when not initialized."""
        with pytest.raises(RuntimeError, match="Service manager not initialized"):
            get_service_manager()

    @patch('src.services.ServiceManager')
    @patch('src.services._service_manager', None)
    def test_init_services_success(self, mock_service_manager_class, mock_llm_config):
        """Test init_services success."""
        config = MagicMock()
        mock_manager = MagicMock()
        mock_service_manager_class.return_value = mock_manager
        mock_manager.initialize_services = AsyncMock(return_value=mock_manager)

        result = asyncio.run(init_services(config))

        assert result == mock_manager
        from src.services import _service_manager
        assert _service_manager == mock_manager

    @patch('src.services.ServiceManager')
    @patch('src.services._service_manager', None)
    def test_init_services_sets_global_manager(self, mock_service_manager_class, mock_llm_config):
        """Test init_services sets global manager."""
        config = MagicMock()
        mock_manager = MagicMock()
        mock_service_manager_class.return_value = mock_manager
        mock_manager.initialize_services = AsyncMock(return_value=mock_manager)

        asyncio.run(init_services(config))

        result = get_service_manager()

        assert result == mock_manager