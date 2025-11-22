"""
Pytest configuration and fixtures for integration tests.

These integration tests use real services and require proper environment setup:
- GITHUB_TOKEN: GitHub API token for repository access
- OLLAMA_HOST: Ollama server URL (default: http://localhost:11434)
- TEST_ISSUE_URL: Base URL for test repository issues
- MCP_SERVER_URL: MCP server URL (optional)
"""

import pytest
import os


@pytest.fixture(scope="session", autouse=True)
def validate_integration_test_environment():
    """Validate that required environment variables are set for integration tests."""
    required_vars = ['GITHUB_TOKEN', 'TEST_ISSUE_URL']

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)


    # Optional but recommended variables
    recommended_vars = ['OLLAMA_HOST', 'MCP_SERVER_URL']
    for var in recommended_vars:
        if not os.getenv(var):
            print(f"Warning: {var} not set - some integration tests may be skipped")


@pytest.fixture(scope="session")
def integration_config():
    """Provide integration test configuration."""
    return {
        "github_token": os.getenv("GITHUB_TOKEN"),
        "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        "test_issue_url": os.getenv("TEST_ISSUE_URL"),
        "mcp_server_url": os.getenv("MCP_SERVER_URL"),
        "test_repo_owner": os.getenv("TEST_REPO_OWNER", "test-owner"),
        "test_repo_name": os.getenv("TEST_REPO_NAME", "test-repo")
    }


@pytest.fixture(scope="function")
def mock_integration_failures():
    """Fixture to simulate various integration failure scenarios."""
    from unittest.mock import patch, AsyncMock

    def mock_service_failure(service_name):
        """Mock a specific service failure."""
        if service_name == "github":
            from src.services import GitHubClient
            with patch.object(GitHubClient, 'health_check', new_callable=AsyncMock, return_value=False):
                yield
        elif service_name == "ollama":
            from src.services import OllamaClient
            with patch.object(OllamaClient, 'health_check', new_callable=AsyncMock, return_value=False):
                yield
        elif service_name == "mcp":
            from src.services import MCPClient
            with patch.object(MCPClient, 'health_check', new_callable=AsyncMock, return_value=False):
                yield

    return mock_service_failure


@pytest.fixture(scope="function")
def mock_network_delays():
    """Fixture to simulate network delays in integration tests."""
    import asyncio
    from unittest.mock import patch

    def mock_delay(delay_seconds=1.0):
        """Add artificial delay to simulate network latency."""
        original_run_in_executor = asyncio.AbstractEventLoop.run_in_executor

        async def delayed_run_in_executor(loop, executor, func, *args, **kwargs):
            await asyncio.sleep(delay_seconds)
            return await original_run_in_executor(loop, executor, func, *args, **kwargs)

        with patch.object(asyncio.AbstractEventLoop, 'run_in_executor', side_effect=delayed_run_in_executor):
            yield

    return mock_delay


@pytest.fixture(scope="function")
def mock_partial_service_outages():
    """Fixture to simulate partial service outages."""
    from unittest.mock import patch, AsyncMock

    def mock_intermittent_failure(service_name, failure_rate=0.5):
        """Mock intermittent service failures."""
        import random

        def intermittent_health_check(self):
            return random.random() > failure_rate

        if service_name == "github":
            from src.services import GitHubClient
            with patch.object(GitHubClient, 'health_check', new_callable=AsyncMock, side_effect=intermittent_health_check):
                yield
        elif service_name == "ollama":
            from src.services import OllamaClient
            with patch.object(OllamaClient, 'health_check', new_callable=AsyncMock, side_effect=intermittent_health_check):
                yield
        elif service_name == "mcp":
            from src.services import MCPClient
            with patch.object(MCPClient, 'health_check', new_callable=AsyncMock, side_effect=intermittent_health_check):
                yield

    return mock_intermittent_failure


@pytest.fixture(scope="function")
def integration_test_isolation():
    """Ensure integration tests don't interfere with each other."""
    # Reset any global state that might persist between tests
    from src.circuit_breaker import circuit_breakers

    # Reset circuit breakers
    for cb in circuit_breakers.values():
        cb._reset()

    # Clear any cached service instances
    from src.services import _service_manager
    if _service_manager is not None:
        # Force recreation of service manager for next test
        import src.services
        src.services._service_manager = None

    yield

    # Cleanup after test
    src.services._service_manager = None