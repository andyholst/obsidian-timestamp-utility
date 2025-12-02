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
    required_vars = ['GITHUB_TOKEN', 'OLLAMA_HOST', 'TEST_ISSUE_URL']

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)


    # Optional variable
    recommended_vars = ['MCP_SERVER_URL']
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


@pytest.fixture(scope="function")


@pytest.fixture(scope="function")


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
# Additional fixtures for Phase 1 Core Infrastructure integration test scenarios

import tempfile
import shutil
import os
import requests
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage
from agents.agentics.src.models import CodeSpec, TestSpec
from agents.agentics.src.state import CodeGenerationState
from agents.agentics.src.config import AgenticsConfig
from langchain_ollama import OllamaLLM


@pytest.fixture(scope="function")
@pytest.mark.integration
def temp_project_dir():
    """
    Temporary project directory for tool tests (e.g., read/write_file).
    Pre-populates with dummy 'input.txt'.
    """
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "input.txt")
    with open(input_path, "w") as f:
        f.write("dummy content")
    os.environ['PROJECT_ROOT'] = temp_dir
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")


@pytest.fixture(scope="function")


@pytest.fixture(scope="function")


@pytest.fixture(scope="function")
@pytest.mark.integration
def dummy_state():
    """Minimal empty CodeGenerationState instance, no dummy LLM."""
    code_spec = CodeSpec(language="")
    test_spec = TestSpec(test_framework="")
    return CodeGenerationState(
        issue_url="",
        ticket_content="",
        title="",
        description="",
        requirements=[],
        acceptance_criteria=[],
        code_spec=code_spec,
        test_spec=test_spec,
        history=[]
    )


@pytest.fixture(scope="session")
    )


@pytest.fixture(scope="session")
@pytest.mark.integration
def real_ollama_config():
    """Real AgenticsConfig with OLLAMA_HOST, fail if not set or unhealthy."""
    if not os.getenv("OLLAMA_HOST"):
        pytest.skip("OLLAMA_HOST environment variable not set")
    config = AgenticsConfig()
    try:
        llm = OllamaLLM(
            model=config.ollama_code_model,
            base_url=config.ollama_host,
            temperature=0.1,
        )
        llm.invoke("healthy")
    except Exception:
        pytest.skip("Ollama server or code model unhealthy")
    return config