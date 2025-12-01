import pytest_asyncio
import os
import pytest
import tempfile
import shutil
pytest_plugins = ("pytest_asyncio",)
from unittest.mock import patch, AsyncMock
from src.circuit_breaker import circuit_breakers
from src.services import GitHubClient
from src.config import init_config, AgenticsConfig

# Import enhanced mock fixtures
from ..fixtures.mock_github_responses import (
    create_github_client_mock,
    create_github_client_with_errors,
    create_github_error_responses,
    create_github_paginated_responses,
    create_github_webhook_payloads
)
from ..fixtures.mock_llm_responses import (
    create_process_llm_mock_responses,
    create_code_generator_mock_responses,
    create_streaming_llm_mock,
    create_llm_error_scenarios,
    create_llm_batch_responses,
    create_llm_with_memory,
    create_multimodal_llm_mock,
    create_llm_with_token_limits
)
from ..fixtures.mock_refactored_components import (
    create_mock_service_manager,
    create_enhanced_mcp_client_mock,
    create_mcp_error_scenarios,
    create_mcp_with_rate_limiting,
    create_mcp_streaming_responses,
    patch_environment_variables,
    patch_circuit_breakers,
    patch_health_monitor,
    create_comprehensive_mock_context
)

# Real project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))


@pytest.fixture(autouse=True)
def reset_circuit_breakers():
    """Reset all circuit breakers before each test to prevent state pollution"""
    for cb in circuit_breakers.values():
        cb._reset()
    yield


@pytest.fixture(autouse=True)
def mock_github_token():
    """Mock GITHUB_TOKEN environment variable for tests"""
    original = os.environ.get('GITHUB_TOKEN')
    os.environ['GITHUB_TOKEN'] = 'mock_token'
    yield
    if original is not None:
        os.environ['GITHUB_TOKEN'] = original
    else:
        os.environ.pop('GITHUB_TOKEN', None)


@pytest.fixture(autouse=True)
def mock_github_health_check():
    """Mock GitHub health check to return True if client exists, False if None"""
    async def mock_health_check(self):
        return self._client is not None

    with patch.object(GitHubClient, 'health_check', mock_health_check):
        yield


@pytest.fixture(autouse=True)
def mock_service_health():
    """Mock service health checks to always return healthy"""
    from unittest.mock import MagicMock
    from src.circuit_breaker import ServiceHealthMonitor
    mock_monitor = MagicMock(spec=ServiceHealthMonitor)
    mock_monitor.is_service_healthy.return_value = True
    with patch('src.services.get_health_monitor', return_value=mock_monitor):
        yield


@pytest.fixture(scope="function")
def mock_github_client():
    """Provide a comprehensive GitHub client mock for testing."""
    return create_github_client_mock()


@pytest.fixture(scope="function")
def mock_github_client_with_errors():
    """Provide a GitHub client mock that can simulate error conditions."""
    return create_github_client_with_errors()


@pytest.fixture(scope="function")
def mock_github_errors():
    """Provide GitHub error response mocks."""
    return create_github_error_responses()


@pytest.fixture(scope="function")
def mock_github_pagination():
    """Provide GitHub pagination mocks."""
    return create_github_paginated_responses()


@pytest.fixture(scope="function")
def mock_github_webhooks():
    """Provide GitHub webhook payload mocks."""
    return create_github_webhook_payloads()


@pytest.fixture(scope="function")
def mock_process_llm_responses():
    """Provide ProcessLLM agent mock responses."""
    return create_process_llm_mock_responses()


@pytest.fixture(scope="function")
def mock_code_generator_responses():
    """Provide CodeGenerator agent mock responses."""
    return create_code_generator_mock_responses()


@pytest.fixture(scope="function")
def mock_streaming_llm():
    """Provide a streaming LLM mock."""
    return create_streaming_llm_mock()


@pytest.fixture(scope="function")
def mock_llm_errors():
    """Provide LLM error scenario mocks."""
    return create_llm_error_scenarios()


@pytest.fixture(scope="function")
def mock_llm_batch():
    """Provide LLM batch processing mocks."""
    return create_llm_batch_responses()


@pytest.fixture(scope="function")
def mock_llm_with_memory():
    """Provide an LLM mock with conversation memory."""
    return create_llm_with_memory()


@pytest.fixture(scope="function")
def mock_multimodal_llm():
    """Provide a multimodal LLM mock."""
    return create_multimodal_llm_mock()


@pytest.fixture(scope="function")
def mock_llm_with_limits():
    """Provide an LLM mock with token limits."""
    return create_llm_with_token_limits()


@pytest.fixture(scope="function")
def mock_service_manager_comprehensive():
    """Provide a comprehensive service manager mock."""
    return create_mock_service_manager()


@pytest.fixture(scope="function")
def mock_enhanced_mcp_client():
    """Provide an enhanced MCP client mock with comprehensive tools."""
    return create_enhanced_mcp_client_mock()


@pytest.fixture(scope="function")
def mock_mcp_errors():
    """Provide MCP error scenario mocks."""
    return create_mcp_error_scenarios()


@pytest.fixture(scope="function")
def mock_mcp_rate_limited():
    """Provide an MCP client mock with rate limiting."""
    return create_mcp_with_rate_limiting()


@pytest.fixture(scope="function")
def mock_mcp_streaming():
    """Provide an MCP client mock with streaming responses."""
    return create_mcp_streaming_responses()


@pytest.fixture(scope="function")
def mock_environment():
    """Context manager for patching environment variables."""
    return patch_environment_variables()


@pytest.fixture(scope="function")
def mock_circuit_breaker_patch():
    """Context manager for patching circuit breakers."""
    return patch_circuit_breakers()


@pytest.fixture(scope="function")
def mock_health_monitor_patch():
    """Context manager for patching health monitor."""
    return patch_health_monitor()


@pytest.fixture(scope="function")
def comprehensive_mock_context():
    """Context manager providing comprehensive mocking for all components."""
    return create_comprehensive_mock_context()


@pytest.fixture
def src_backup(request, tmp_path):
    """
    Fixture to backup and restore the src directory for each test.
    If the test uses temp_project_dir, it operates on that; otherwise, it creates a new temp dir.
    """
    if 'temp_project_dir' in request.fixturenames:
        project_dir = request.getfixturevalue('temp_project_dir')
    else:
        project_dir = tmp_path / "project"
        shutil.copytree(PROJECT_ROOT, str(project_dir), dirs_exist_ok=True)

    src_dir = os.path.join(project_dir, 'src')
    backup_dir = tempfile.mkdtemp(prefix='src_backup_')
    shutil.copytree(src_dir, backup_dir, ignore=shutil.ignore_patterns('logs'))
    yield project_dir
    shutil.rmtree(src_dir)
    shutil.copytree(backup_dir, src_dir)
    shutil.rmtree(backup_dir)
@pytest_asyncio.fixture
async def service_manager():
    """Create a service manager with initialized real services for testing."""
    from src.config import get_config
    from src.services import ServiceManager
    config = get_config()
    sm = ServiceManager(config)
    await sm.initialize_services()
    return sm


@pytest.fixture(scope="session", autouse=True)
def init_unit_test_config():
    # Initialize config with test defaults
    init_config(AgenticsConfig(
        github_token=os.getenv("GITHUB_TOKEN", "test_token"),
        ollama_host="http://localhost:11434"
    ))
