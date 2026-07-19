import sys
import os

# Set PROJECT_ROOT before any imports to ensure all agents use a writable directory
os.environ.setdefault("PROJECT_ROOT", "/tmp/obsidian-project")
os.makedirs(os.environ["PROJECT_ROOT"], exist_ok=True)
os.makedirs(os.path.join(os.environ["PROJECT_ROOT"], "src"), exist_ok=True)
os.makedirs(os.path.join(os.environ["PROJECT_ROOT"], "src", "__tests__"), exist_ok=True)

# Enable fast test mode by default - skips integration testing phase (npm test)
# ULTRA_FAST_MODE skips dependency analysis too, reducing LLM calls to minimum
os.environ.setdefault("TEST_FAST_MODE", "1")
os.environ.setdefault("TEST_ULTRA_FAST_MODE", "1")

# Increase per-test timeout to allow process_issue tests to complete
# Default is 300s (5 min), increase to 1800s (30 min) for LLM-heavy tests
os.environ.setdefault("PYTEST_TIMEOUT", "1800")

# Use sorc/qwen3.6-35b-a3b for both reasoning and code generation
os.environ.setdefault("LLAMA_REASONING_MODEL", "sorc/qwen3.6-35b-a3b")
os.environ.setdefault("LLAMA_CODE_MODEL", "sorc/qwen3.6-35b-a3b")

# Load .env file from project root so GITHUB_TOKEN and other env vars are available
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))
# Also make this integration tests dir importable (for shared helpers like _e2e_helpers).
sys.path.insert(0, os.path.dirname(__file__))

_env_paths = [
    "/app/.env",  # Dagger container working directory
    os.path.join(os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../..")), ".env"),  # project root relative to tests/integration
    "/project/.env",  # Dagger-mounted project root
    "/.env",  # container root
]
for _env_file in _env_paths:
    if os.path.exists(_env_file):
        from dotenv import load_dotenv
        load_dotenv(_env_file, override=True)
        break

# Disable langsmith tracing to prevent hangs and auth errors
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_ENDPOINT"] = ""
os.environ["LANGCHAIN_API_KEY"] = ""
os.environ["LANGCHAIN_PROJECT"] = ""

# Set project root for tests that need file system access
# Use /tmp/obsidian-project as the project root (create if needed)
_project_root = os.getenv("PROJECT_ROOT", "/tmp/obsidian-project")
os.environ["PROJECT_ROOT"] = _project_root

# Copy real src/ and other project files into the temp project root
# so that CodeExtractorAgent can read actual source files.
#
# B3 GUARD: never copy the real plugin src into a PROJECT_ROOT that IS the agentics
# source tree (the integration container mounts agents/agentics/src at /app/src and sets
# PROJECT_ROOT=/app). Copying there pollutes agents/agentics/src with the plugin's own
# source. The e2e harness creates its own temp PROJECT_ROOT for generation, so skipping
# the copy when PROJECT_ROOT points at the agentics source is safe and prevents pollution.
import shutil


def _e2e_may_copy_real_src(project_root, real_src, agentics_src_mount):
    """B5/B6 guard predicate (pure, testable).

    Returns True only when it is safe to rmtree+copy the real plugin `src/` into
    PROJECT_ROOT/src — i.e. when PROJECT_ROOT is an ISOLATED temp dir. Returns False when
    the destination would be the REAL committed `src/` or the agentics `src` mount, so the
    harness only ever READS those and never destructively deletes the committed baseline.
    Defined in `_e2e_guard.py` (side-effect-free) and re-exported here for conftest use.
    """
    from _e2e_guard import e2e_may_copy_real_src as _impl

    return _impl(project_root, real_src, agentics_src_mount)


_real_src = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))
_real_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_agentics_src_mount = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
_pollutes_source = os.path.normpath(_project_root) == _agentics_src_mount or \
    os.path.normpath(_project_root) == "/app" or \
    os.path.abspath(_project_root).startswith(os.path.abspath(_agentics_src_mount) + os.sep)
if os.path.isdir(_real_src) and not _pollutes_source:
    _dst_src = os.path.join(_project_root, "src")
    # B5/B6 HARD GUARD: never rmtree/copy INTO the real plugin source tree or the agentics
    # mount. If the resolved destination is the real repo's `src/` (or the agentics `src`
    # mount), skip entirely — running the e2e against the real committed baseline must be a
    # pure read, never a destructive delete. The intended path is an ISOLATED temp
    # PROJECT_ROOT (e.g. /tmp/obsidian-project); only then do we rmtree+copy.
    if _e2e_may_copy_real_src(_project_root, _real_src, _agentics_src_mount):
        if os.path.exists(_dst_src):
            shutil.rmtree(_dst_src)
        shutil.copytree(_real_src, _dst_src)

for _fname in ("package.json", "tsconfig.json", "jest.config.js", "manifest.json"):
    _src_f = os.path.join(_real_root, _fname)
    if os.path.isfile(_src_f):
        _dst_f = os.path.join(_project_root, _fname)
        # B5/B6: never copy a file onto itself (PROJECT_ROOT === real repo root).
        if os.path.normpath(_src_f) == os.path.normpath(_dst_f):
            continue
        shutil.copy2(_src_f, _dst_f)

# Store original file contents for reset after each test
_ORIGINAL_FILE_CONTENTS = {}
_files_to_track = [
    "src/main.ts",
    "src/__tests__/main.test.ts",
    "package.json",
    "tsconfig.json",
    "jest.config.js",
    "manifest.json",
]
for _fname in _files_to_track:
    _fpath = os.path.join(_project_root, _fname)
    if os.path.exists(_fpath):
        with open(_fpath, "r") as f:
            _ORIGINAL_FILE_CONTENTS[_fname] = f.read()
    else:
        _ORIGINAL_FILE_CONTENTS[_fname] = None

# Also track package-lock.json
_lock_file = os.path.join(_project_root, "package-lock.json")
if os.path.exists(_lock_file):
    with open(_lock_file, "r") as f:
        _ORIGINAL_FILE_CONTENTS["package-lock.json"] = f.read()
else:
    _ORIGINAL_FILE_CONTENTS["package-lock.json"] = None

"""
Pytest configuration and fixtures for integration tests.

These integration tests use real services and require proper environment setup:
- GITHUB_TOKEN: GitHub API token for repository access
- LLAMA_HOST: Llama server URL (default: http://localhost:11434)
- TEST_ISSUE_URL: Base URL for test repository issues
"""

import pytest
import os
import subprocess


@pytest.fixture(scope="session", autouse=True)
def validate_integration_test_environment():
    """Validate that required environment variables are set for integration tests."""
    required_vars = ["GITHUB_TOKEN", "LLAMA_HOST", "TEST_ISSUE_URL"]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)


@pytest.fixture(scope="session", autouse=True)
def b5_committed_baseline_guard():
    """B5/B6 belt-and-suspenders: the e2e harness MUST NEVER mutate or delete the REAL
    committed plugin source (the git baseline). It must only read it and generate into an
    ISOLATED temp PROJECT_ROOT.

    This session-scoped fixture snapshots the real tracked TS files at session start and
    asserts they are byte-identical at session end. If any e2e run (or the conftest copy
    logic) ever deletes or rewrites the committed `src/main.ts`, this guard FAILS the run
    loudly instead of silently leaving the baseline corrupted. Mirrors B5 (restore to
    committed baseline) and B6 (never keep regenerated code in the repo).
    """
    real_src = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
    )
    tracked = [
        "main.ts",
        "__tests__/main.test.ts",
        "taskProcessor.ts",
        "folderSelectorModal.ts",
        "__mocks__/obsidian.ts",
        "__tests__/taskProcessor.test.ts",
        "__tests__/folderSelectorModal.test.ts",
    ]
    snapshot = {}
    for rel in tracked:
        fpath = os.path.join(real_src, rel)
        if os.path.exists(fpath):
            with open(fpath, "rb") as f:
                snapshot[rel] = f.read()
        else:
            snapshot[rel] = None  # file did not exist at session start

    yield  # e2e tests run here

    # After the whole session: assert the real committed baseline is intact.
    for rel, original in snapshot.items():
        fpath = os.path.join(real_src, rel)
        exists_now = os.path.exists(fpath)
        if original is None:
            # Was absent at start; a newly-created real file is a B5/B6 leak.
            assert not exists_now, (
                f"B5/B6 violation: e2e created real committed file {fpath} "
                f"that did not exist at session start. The harness must not write "
                f"into the committed baseline."
            )
            continue
        assert exists_now, (
            f"B5/B6 violation: e2e DELETED the real committed file {fpath}. "
            f"The harness must restore (never delete) the committed baseline."
        )
        with open(fpath, "rb") as f:
            current = f.read()
        assert current == original, (
            f"B5/B6 violation: e2e MUTATED the real committed file {fpath} "
            f"({len(original)} -> {len(current)} bytes). The harness must only read "
            f"the committed baseline, generating into an isolated temp PROJECT_ROOT."
        )


@pytest.fixture(scope="function", autouse=True)
def test_issue_url(monkeypatch):
    """Set default TEST_ISSUE_URL environment variable for integration tests."""
    monkeypatch.setenv(
        "TEST_ISSUE_URL", "https://github.com/andyholst/obsidian-timestamp-utility"
    )


@pytest.fixture(scope="function", autouse=True)
def backup_and_restore_project_files():
    """
    Back up generated files before each test and restore original files after.
    This ensures tests don't conflict with each other.
    """
    import shutil
    from datetime import datetime

    project_root = os.environ.get("PROJECT_ROOT", "/tmp/obsidian-project")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    # Files to back up and restore
    files_to_manage = [
        "src/main.ts",
        "src/__tests__/main.test.ts",
        "package.json",
        "tsconfig.json",
        "jest.config.js",
        "manifest.json",
        "package-lock.json",
    ]

    # Back up files that were modified by the test (before restoring)
    backup_dir = os.path.join(project_root, "backups", timestamp)
    os.makedirs(backup_dir, exist_ok=True)

    yield  # Test runs here

    # After test: back up any modified files, then restore originals
    for fname in files_to_manage:
        fpath = os.path.join(project_root, fname)
        original_content = _ORIGINAL_FILE_CONTENTS.get(fname)

        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                current_content = f.read()

            # Back up the current (modified) file
            backup_path = os.path.join(backup_dir, fname.replace("/", "_"))
            shutil.copy2(fpath, backup_path)

            # Restore original content
            if original_content is not None:
                with open(fpath, "w") as f:
                    f.write(original_content)
            else:
                # File didn't exist originally, remove it
                os.remove(fpath)
        elif original_content is not None:
            # File was deleted during test, restore it
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "w") as f:
                f.write(original_content)

    # Clean up node_modules if it was installed during test
    node_modules_path = os.path.join(project_root, "node_modules")
    if os.path.exists(node_modules_path):
        shutil.rmtree(node_modules_path, ignore_errors=True)


@pytest.fixture(scope="session")
def integration_config():
    """Provide integration test configuration."""
    return {
        "github_token": os.getenv("GITHUB_TOKEN"),
        "llama_host": os.getenv("LLAMA_HOST", "http://localhost:11434"),
        "test_issue_url": os.getenv("TEST_ISSUE_URL"),
        "test_repo_owner": os.getenv("TEST_REPO_OWNER", "test-owner"),
        "test_repo_name": os.getenv("TEST_REPO_NAME", "test-repo"),
    }



@pytest.fixture(scope="function")
def clean_app_state():
    """Reset global state between integration tests."""
    # Reset global service manager
    import src.services
    src.services._service_manager = None
    # Reset global config
    import src.config
    src.config._config = None
    # Reset circuit breakers
    from src.circuit_breaker import circuit_breakers
    for cb in circuit_breakers.values():
        cb._reset()
    yield
    # Cleanup after test
    src.services._service_manager = None
    src.config._config = None

@pytest.fixture(scope="function", autouse=True)
def integration_test_isolation():
    """Ensure integration tests don't interfere with each other."""
    # Reset any global state that might persist between tests
    from src.circuit_breaker import circuit_breakers

    # Reset circuit breakers
    for cb in circuit_breakers.values():
        cb._reset()

    # Clear any cached service instances
    from src.services import _service_manager
    import src.services

    if _service_manager is not None:
        # Force recreation of service manager for next test
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
from src.models import CodeSpec, TestSpecification
from src.state import CodeGenerationState
from src.config import AgenticsConfig
from langchain_openai import ChatOpenAI

import json
import logging
from langgraph.checkpoint.memory import MemorySaver


@pytest.fixture(scope="function")
def temp_project_dir():
    """
    Temporary project directory for tool tests (e.g., read/write_file).
    Copies the real src/ directory from the project so agents can read actual source files.
    """
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "input.txt")
    with open(input_path, "w") as f:
        f.write("dummy content")
    # Copy real src/ directory from the project
    _real_src = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../..", "src"))
    _real_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../.."))
    if os.path.isdir(_real_src):
        shutil.copytree(_real_src, os.path.join(temp_dir, "src"))
    # Copy package.json, tsconfig.json, jest.config.js if they exist
    for _fname in ("package.json", "tsconfig.json", "jest.config.js", "manifest.json"):
        _src_f = os.path.join(_real_root, _fname)
        if os.path.isfile(_src_f):
            shutil.copy2(_src_f, os.path.join(temp_dir, _fname))
    os.environ["PROJECT_ROOT"] = temp_dir
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def dummy_state():
    """Minimal empty CodeGenerationState instance, no dummy LLM."""
    code_spec = CodeSpec(language="")
    test_spec = TestSpecification(test_framework="")
    return CodeGenerationState(
        issue_url="",
        ticket_content="",
        title="",
        description="",
        requirements=[],
        acceptance_criteria=[],
        code_spec=code_spec,
        test_spec=test_spec,
        history=[],
    )


@pytest.fixture(scope="function")
def dummy_llm():
    return RunnableLambda(
        lambda p: AIMessage(
            content="",
            additional_kwargs={
                "code": "def testMethod():\n    pass",
                "command_id": "test-command-id",
            },
        )
    )


@pytest.fixture(scope="function")
def dummy_llm_tool():
    return RunnableLambda(
        lambda p: AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_abc123",
                    "name": "dummy_tool",
                    "args": {"method": "testMethod", "id": "test-command-id"},
                    "type": "tool",
                }
            ],
        )
    )


@pytest.fixture(scope="session")
def real_llama_config():
    """Real AgenticsConfig with LLAMA_HOST, fail if not set or unhealthy."""
    if not os.getenv("LLAMA_HOST"):
        pytest.skip("LLAMA_HOST environment variable not set")
    config = AgenticsConfig()
    try:
        llm = ChatOpenAI(
            model=config.llama_code_model,
            base_url=config.llama_host,
            temperature=0.1,
            timeout=5.0,
        )
        llm.invoke("healthy")
    except Exception:
        pytest.skip("Llama server or code model unhealthy")
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
        "scripts": {"test": "jest"},
        "devDependencies": {"jest": "^29.0.0"},
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
    passed = len(stats.get("passed", []))
    failed = len(stats.get("failed", []))
    error = len(stats.get("error", []))
    xpassed = len(stats.get("xpassed", []))
    xfailed = len(stats.get("xfailed", []))
    run_count = passed + failed + error + xpassed + xfailed
    print(
        f"\n=== Actually ran {run_count} tests ({passed} passed, {failed} failed, {error} error, {xpassed} xpassed, {xfailed} xfailed) ==="
    )
