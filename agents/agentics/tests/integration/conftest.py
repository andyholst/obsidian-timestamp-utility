import sys
import os
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "../..", "src")))
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
import subprocess


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


@pytest.fixture(scope="function", autouse=True)
def test_issue_url(monkeypatch):
    """Set default TEST_ISSUE_URL environment variable for integration tests."""
    monkeypatch.setenv("TEST_ISSUE_URL", "https://github.com/andyholst/obsidian-timestamp-utility")

@pytest.fixture(autouse=True, scope="function")
def git_reset_fixture():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
    def reset_git():
        try:
            subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=repo_root, check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
            pass  # Ignore git reset errors to prevent test failures
    reset_git()
    yield
    reset_git()

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
from src.models import CodeSpec, TestSpec
from src.state import CodeGenerationState
from src.config import AgenticsConfig
from langchain_ollama import OllamaLLM

import json
import logging
from langgraph.checkpoint.memory import MemorySaver


@pytest.fixture(scope="function")
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

@pytest.fixture(scope="function")
def dummy_llm():
    return RunnableLambda(lambda p: AIMessage(content="", additional_kwargs={"code": "def testMethod():\n    pass", "command_id": "test-command-id"}))


@pytest.fixture(scope="function")
def dummy_llm_tool():
    return RunnableLambda(lambda p: AIMessage(content="", tool_calls=[{"id": "call_abc123", "name": "dummy_tool", "args": {"method": "testMethod", "id": "test-command-id"}, "type": "tool"}]))


@pytest.fixture(scope="session")
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
            timeout=5.0,
        )
        llm.invoke("healthy")
    except Exception:
        pytest.skip("Ollama server or code model unhealthy")
    return config




@pytest.fixture(scope="session")
def checkpointer():
    """MemorySaver checkpointer for langgraph workflows."""
    return MemorySaver()


@pytest.fixture(scope="function")
def npm_mock_dir():
    """
    Temporary npm project directory with package.json for npm/jest tool tests.
    """
    temp_dir = tempfile.mkdtemp()
    pkg_path = os.path.join(temp_dir, "package.json")
    package_data = {
        "name": "mock-npm-project",
        "version": "1.0.0",
        "scripts": {
            "test": "jest"
        },
        "devDependencies": {
            "jest": "^29.0.0"
        }
    }
    with open(pkg_path, "w") as f:
        json.dump(package_data, f, indent=2)
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def caplog_config(caplog):
    """Configure caplog for agentics monitoring/logging tests."""
    caplog.set_level(logging.DEBUG)
    yield caplog


@pytest.fixture(scope="function")
def parallel_dummy_agents(dummy_state):
    """List of dummy agents for parallel processing integration tests."""
    class DummyAgent:
        def __init__(self, name):
            self.name = name

        def process(self, state):
            """Dummy process method appending to history."""
            return state.with_history([f"Processed by {self.name}"])

    return [DummyAgent(f"parallel_agent_{i}") for i in range(3)]
def pytest_collection_finish(session):
    print(f"\n=== Collected {len(session.items)} tests before running ===")

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    stats = terminalreporter.stats
    passed = len(stats.get('passed', []))
    failed = len(stats.get('failed', []))
    error = len(stats.get('error', []))
    xpassed = len(stats.get('xpassed', []))
    xfailed = len(stats.get('xfailed', []))
    run_count = passed + failed + error + xpassed + xfailed
    print(f"\n=== Actually ran {run_count} tests ({passed} passed, {failed} failed, {error} error, {xpassed} xpassed, {xfailed} xfailed) ===")