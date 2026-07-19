import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from src.services import (
    ServiceClient,
    LLMClient,
    GitHubClient,
    ServiceManager,
    get_service_manager,
    init_services,
    _service_manager,
)
from src.exceptions import LLMError, GitHubError, ServiceUnavailableError
from src.config import LLMConfig
from src.circuit_breaker import CircuitBreaker, ServiceHealthMonitor
from tests.fixtures.mock_circuit_breaker import (
    create_mock_circuit_breaker,
    patch_circuit_breakers,
)
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
        num_ctx=2048,
        num_predict=512,
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

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    def test_service_client_initialization(
        self,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test ServiceClient initialization."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = ConcreteServiceClient("test_service")

        assert client.name == "test_service"
        assert client.circuit_breaker == mock_circuit_breaker
        assert client.health_monitor == mock_health_monitor

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    def test_service_client_abstract_methods(
        self,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test that ServiceClient abstract methods raise NotImplementedError."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = ConcreteServiceClient("test_service")

        # These should work since we implemented them
        assert asyncio.run(client.health_check()) is True
        assert client.is_available() is True


class TestLLMClient:
    """Test LLMClient functionality."""

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.ChatOpenAI")
    def test_llm_client_initialization_success(
        self,
        mock_chat_openai_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_llm_config,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test LLMClient initialization with valid config."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_llm_instance = MagicMock()
        mock_chat_openai_class.return_value = mock_llm_instance

        client = LLMClient(mock_llm_config)

        assert client.config == mock_llm_config
        # With lazy initialization, _client is None until first use
        assert client._client is None
        # Accessing the client property triggers initialization
        assert client.client == mock_llm_instance
        mock_chat_openai_class.assert_called_once_with(
            model="test-model",
            base_url="http://test.com",
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            min_p=0.0,
            request_timeout=30,
            extra_params={
                "presence_penalty": 1.0,
                "num_ctx": 2048,
                "num_predict": 512,
            },
        )

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.ChatOpenAI")
    def test_llm_client_initialization_failure(
        self,
        mock_chat_openai_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_llm_config,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test LLMClient initialization failure."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_chat_openai_class.side_effect = Exception("Init failed")

        client = LLMClient(mock_llm_config)

        assert client._client is None

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.ChatOpenAI")
    def test_llm_client_health_check_success(
        self,
        mock_chat_openai_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_llm_config,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test LLMClient health check success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = "Hello response"
        mock_chat_openai_class.return_value = mock_llm_instance

        client = LLMClient(mock_llm_config)

        # Mock asyncio loop
        async def mock_run_in_executor(*args, **kwargs):
            return "Hello response"

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = mock_run_in_executor

            result = asyncio.run(client.health_check())

            assert result is True

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.ChatOpenAI")
    def test_llm_client_health_check_no_client(
        self,
        mock_chat_openai_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_llm_config,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test LLMClient health check when client is None."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_chat_openai_class.side_effect = Exception("Init failed")

        client = LLMClient(mock_llm_config)

        result = asyncio.run(client.health_check())

        assert result is False

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.ChatOpenAI")
    def test_llm_client_health_check_exception(
        self,
        mock_chat_openai_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_llm_config,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test LLMClient health check with exception."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_llm_instance = MagicMock()
        mock_chat_openai_class.return_value = mock_llm_instance

        client = LLMClient(mock_llm_config)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.side_effect = Exception(
                "Health check failed"
            )

            result = asyncio.run(client.health_check())

            assert result is False

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.ChatOpenAI")
    def test_llm_client_is_available(
        self,
        mock_chat_openai_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_llm_config,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test LLMClient is_available method."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_llm_instance = MagicMock()
        mock_chat_openai_class.return_value = mock_llm_instance

        client = LLMClient(mock_llm_config)

        result = client.is_available()

        assert result is True
        mock_health_monitor.is_service_healthy.assert_called_once_with("llm")

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.ChatOpenAI")
    def test_llm_client_is_available_no_client(
        self,
        mock_chat_openai_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_llm_config,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test LLMClient is_available when client is None."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_chat_openai_class.side_effect = Exception("Init failed")

        client = LLMClient(mock_llm_config)

        result = client.is_available()

        assert result is False

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.ChatOpenAI")
    def test_llm_client_invoke_success(
        self,
        mock_chat_openai_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_llm_config,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test LLMClient invoke method success."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = "LLM response"
        mock_chat_openai_class.return_value = mock_llm_instance

        client = LLMClient(mock_llm_config)

        result = client.invoke("Test prompt")

        assert result == "LLM response"
        mock_llm_instance.invoke.assert_called_once_with("Test prompt")

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.ChatOpenAI")
    def test_llm_client_invoke_not_available(
        self,
        mock_chat_openai_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_llm_config,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test LLMClient invoke when service not available."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor
        mock_health_monitor.is_service_healthy.return_value = False

        mock_llm_instance = MagicMock()
        mock_chat_openai_class.return_value = mock_llm_instance

        client = LLMClient(mock_llm_config)

        with pytest.raises(
            LLMError, match="LLM service \\(test-model\\) is not available"
        ):
            client.invoke("Test prompt")


class TestGitHubClient:
    """Test GitHubClient functionality."""

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.Github")
    @patch("src.services.Auth")
    def test_github_client_initialization_success(
        self,
        mock_auth_class,
        mock_github_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_github_token,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
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

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.Github")
    @patch("src.services.Auth")
    def test_github_client_initialization_failure(
        self,
        mock_auth_class,
        mock_github_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_github_token,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test GitHubClient initialization failure."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_github_class.side_effect = Exception("Init failed")

        client = GitHubClient(mock_github_token)

        assert client._client is None

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.Github")
    @patch("src.services.Auth")
    def test_github_client_health_check_success(
        self,
        mock_auth_class,
        mock_github_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_github_token,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
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

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = mock_run_in_executor

            result = asyncio.run(client.health_check())

            assert result is True

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    def test_github_client_health_check_no_client(
        self,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test GitHubClient health check when client is None."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = GitHubClient(None)

        print(f"client type: {type(client)}")
        print(f"client._client: {client._client}")

        print("Before asyncio.run")
        result = asyncio.run(client.health_check())
        print("After asyncio.run")

        assert result is False

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.Github")
    @patch("src.services.Auth")
    def test_github_client_is_available(
        self,
        mock_auth_class,
        mock_github_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_github_token,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test GitHubClient is_available method."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_github_instance = MagicMock()
        mock_github_class.return_value = mock_github_instance

        client = GitHubClient(mock_github_token)

        result = client.is_available()

        assert result is True
        mock_health_monitor.is_service_healthy.assert_called_once_with("github")

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    def test_github_client_is_available_no_client(
        self,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test GitHubClient is_available when client is None."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor

        client = GitHubClient(None)

        result = client.is_available()

        assert result is False

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.Github")
    @patch("src.services.Auth")
    def test_github_client_get_user_success(
        self,
        mock_auth_class,
        mock_github_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_github_token,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
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

    @patch("src.services.get_circuit_breaker")
    @patch("src.services.get_health_monitor")
    @patch("src.services.Github")
    @patch("src.services.Auth")
    def test_github_client_get_user_not_available(
        self,
        mock_auth_class,
        mock_github_class,
        mock_get_health_monitor,
        mock_get_circuit_breaker,
        mock_github_token,
        mock_circuit_breaker,
        mock_health_monitor,
    ):
        """Test GitHubClient get_user when service not available."""
        mock_get_circuit_breaker.return_value = mock_circuit_breaker
        mock_get_health_monitor.return_value = mock_health_monitor
        mock_health_monitor.is_service_healthy.return_value = False

        mock_github_instance = MagicMock()
        mock_github_class.return_value = mock_github_instance

        client = GitHubClient(mock_github_token)

        with pytest.raises(GitHubError, match="GitHub service is not available"):
            client.get_user()


class TestServiceManager:
    """Test ServiceManager functionality."""

    @patch("src.services.get_health_monitor")
    def test_service_manager_initialization(
        self, mock_get_health_monitor, mock_health_monitor
    ):
        """Test ServiceManager initialization."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        manager = ServiceManager(config)

        assert manager.config == config
        assert manager.llm_reasoning is None
        assert manager.llm_code is None
        assert manager.github is None
        assert manager.health_monitor == mock_health_monitor

    @patch("src.services.get_health_monitor")
    def test_service_manager_initialize_services(
        self, mock_get_health_monitor, mock_health_monitor, mock_llm_config
    ):
        """Test ServiceManager initialize_services."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        config.get_reasoning_llm_config.return_value = mock_llm_config
        config.get_code_llm_config.return_value = mock_llm_config
        config.github_token = "test_token"

        manager = ServiceManager(config)

        asyncio.run(manager.initialize_services())

        assert manager.llm_reasoning is not None
        assert manager.llm_code is not None
        assert manager.github is not None

        mock_health_monitor.register_service.assert_any_call(
            "llm_reasoning", manager.llm_reasoning.health_check
        )
        mock_health_monitor.register_service.assert_any_call(
            "llm_code", manager.llm_code.health_check
        )
        mock_health_monitor.register_service.assert_any_call(
            "github", manager.github.health_check
        )

    @patch("src.services.get_health_monitor")
    @patch("src.services.LLMClient")
    @patch("src.services.GitHubClient")
    def test_service_manager_initialize_services_no_github_token(
        self,
        mock_github_class,
        mock_chat_openai_class,
        mock_get_health_monitor,
        mock_health_monitor,
        mock_llm_config,
    ):
        """Test ServiceManager initialize_services without GitHub token."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        config.get_reasoning_llm_config.return_value = mock_llm_config
        config.get_code_llm_config.return_value = mock_llm_config
        config.github_token = None

        mock_llm_reasoning = MagicMock()
        mock_llm_code = MagicMock()

        mock_chat_openai_class.side_effect = [mock_llm_reasoning, mock_llm_code]

        manager = ServiceManager(config)

        asyncio.run(manager.initialize_services())

        assert manager.github is None
        mock_github_class.assert_not_called()

    @patch("src.services.get_health_monitor")
    def test_service_manager_check_services_health(self, mock_get_health_monitor):
        """Test ServiceManager check_services_health."""
        mock_health_monitor = MagicMock()
        mock_get_health_monitor.return_value = mock_health_monitor

        mock_health_monitor.is_service_healthy.side_effect = lambda name: {
            "llm_reasoning": True,
            "llm_code": False,
            "github": True,
        }.get(name, False)

        config = MagicMock()
        manager = ServiceManager(config)

        # Mock services
        mock_llm_reasoning = MagicMock()
        mock_llm_code = MagicMock()
        mock_github = MagicMock()

        manager.llm_reasoning = mock_llm_reasoning
        manager.llm_code = mock_llm_code
        manager.github = mock_github

        result = asyncio.run(manager.check_services_health())

        expected = {
            "llm_reasoning": True,
            "llm_code": False,
            "github": True,
        }
        assert result == expected

    @patch("src.services.get_health_monitor")
    def test_service_manager_check_services_health_none_services(
        self, mock_get_health_monitor, mock_health_monitor
    ):
        """Test ServiceManager check_services_health with None services."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        manager = ServiceManager(config)

        # Ensure services are None
        manager.llm_reasoning = None
        manager.llm_code = None
        manager.github = None

        result = asyncio.run(manager.check_services_health())

        expected = {
            "llm_reasoning": False,
            "llm_code": False,
            "github": False,
        }
        assert result == expected

    @patch("src.services.get_health_monitor")
    def test_service_manager_close_services(
        self, mock_get_health_monitor, mock_health_monitor
    ):
        """Test ServiceManager close_services."""
        mock_get_health_monitor.return_value = mock_health_monitor

        config = MagicMock()
        manager = ServiceManager(config)

        asyncio.run(manager.close_services())


class TestGlobalServiceFunctions:
    """Test global service management functions."""

    @patch("src.services._service_manager", None)
    def test_get_service_manager_not_initialized(self):
        """Test get_service_manager when not initialized."""
        with pytest.raises(RuntimeError, match="Service manager not initialized"):
            get_service_manager()

    @patch("src.services._service_manager", None)
    def test_init_services_success(self, mock_llm_config):
        """Test init_services success."""
        config = MagicMock()

        result = asyncio.run(init_services(config))

        assert result is not None
        from src.services import _service_manager

        assert _service_manager is not None

    @patch("src.services.ServiceManager")
    @patch("src.services._service_manager", None)
    def test_init_services_sets_global_manager(
        self, mock_service_manager_class, mock_llm_config
    ):
        """Test init_services sets global manager."""
        config = MagicMock()
        mock_manager = MagicMock()
        mock_service_manager_class.return_value = mock_manager
        mock_manager.initialize_services = AsyncMock(return_value=mock_manager)

        asyncio.run(init_services(config))

        result = get_service_manager()

        assert result == mock_manager
