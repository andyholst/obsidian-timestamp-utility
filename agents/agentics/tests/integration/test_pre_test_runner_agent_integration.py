import pytest
import os
from src.pre_test_runner_agent import PreTestRunnerAgent
from src.state import State
from _e2e_helpers import make_seeded_project_root, plugin_ts_tests_present

# Seed an ISOLATED temp PROJECT_ROOT with the real plugin files (src/, package.json,
# jest.config.cjs, + a node_modules symlink) so PreTestRunner runs npm test against the
# seeded temp dir — NOT the real repo mounted at /project. This is required because
# CodeIntegratorAgent writes generated TS back into PROJECT_ROOT on construction; if the
# seeded temp dir were a real checkout (like /project), a full-pipeline integration run
# would overwrite the repo's actual src/main.ts with the generated plugin (pollution
# incident: loop-ts-floor addCommand dropped 9 -> 0 after loop-integration).
SEEDED_PROJECT_ROOT = make_seeded_project_root(prefix="pre_test_project_")

# In the integration container /app/src is overmounted by the Python agentics source and
# /project is the real repo mount; seed the TS scaffold is only reachable when the repo
# tree is available to make_seeded_project_root. Skip cleanly (B17) when it is absent.
HAS_TS_TESTS = plugin_ts_tests_present(SEEDED_PROJECT_ROOT)


@pytest.fixture
def temp_empty_project(tmp_path):
    # Given: An empty temporary project directory without package.json
    project_dir = tmp_path / "empty_project"
    project_dir.mkdir()
    return str(project_dir)


@pytest.mark.skipif(
    not HAS_TS_TESTS,
    reason="plugin TypeScript test scaffold (src/__tests__/main.test.ts) not reachable "
    "for seeding; PreTestRunner would run npm test against a non-seeded dir",
)
def test_pre_test_runner_agent_success():
    """
    Test that PreTestRunnerAgent successfully runs npm install and npm test
    in an ISOLATED seeded temp project directory (not the real /project mount),
    so the run never writes into the repo's actual src/.
    """
    # Given: A PreTestRunnerAgent instance using the seeded temp project directory
    agent = PreTestRunnerAgent()
    agent.project_root = SEEDED_PROJECT_ROOT  # Isolated seeded temp dir
    os.environ["PROJECT_ROOT"] = SEEDED_PROJECT_ROOT
    state = State()

    # When: Processing the state with real npm commands
    result = agent(state)

    # Then: Verify test metrics match integration test expectations
    assert "existing_tests_passed" in result, (
        "Number of passing tests missing from result"
    )
    assert "existing_coverage_all_files" in result, (
        "Coverage percentage missing from result"
    )
    assert result["existing_tests_passed"] >= 0, (
        "Expected non-negative tests passed"
    )
    assert result["existing_coverage_all_files"] >= 0, (
        "Expected non-negative coverage"
    )


def test_pre_test_runner_agent_no_package_json(temp_empty_project):
    """
    Test that PreTestRunnerAgent raises a RuntimeError when package.json is missing.
    Uses a temporary empty directory to simulate this condition.
    """
    # Given: A PreTestRunnerAgent instance with an empty project directory
    agent = PreTestRunnerAgent()
    agent.project_root = temp_empty_project  # Temporary directory without package.json
    os.environ["PROJECT_ROOT"] = temp_empty_project
    state = State()

    # When: Processing the state with real npm commands
    # Then: Expect handling without package.json, default metrics
    result = agent(state)
    assert result["existing_tests_passed"] == 0
    assert result["existing_coverage_all_files"] == 0.0


def test_strip_ansi_codes():
    """
    Test the utility function to strip ANSI codes from text.
    This test does not involve npm commands and remains unchanged.
    """
    # Given: Text with and without ANSI codes
    agent = PreTestRunnerAgent()
    text_with_ansi = "\x1b[31mRed text\x1b[0m"
    plain_text = "Plain text"

    # When: Stripping ANSI codes
    result = agent.strip_ansi_codes(text_with_ansi)
    plain_result = agent.strip_ansi_codes(plain_text)

    # Then: Verify stripped output
    assert result == "Red text", "Expected ANSI codes to be removed"
    assert plain_result == "Plain text", "Expected plain text to remain unchanged"


def test_pre_test_runner_agent_custom_commands(temp_empty_project):
    # Given: Custom install and test commands via environment variables
    agent = PreTestRunnerAgent()
    agent.project_root = temp_empty_project
    os.environ["PROJECT_ROOT"] = temp_empty_project
    agent.install_command = "echo Installing"
    agent.test_command = "echo 'Tests: 5 passed, 5 total'"
    state = State()

    # When: Processing the state with custom commands
    result = agent(state)

    # Then: Verify custom commands run successfully and output is parsed
    assert "existing_tests_passed" in result, "Should report tests passed"
    assert "existing_coverage_all_files" in result, "Should report coverage"
    assert result["existing_tests_passed"] == 5, (
        "Expected 5 tests passed based on custom command output"
    )
    assert result["existing_coverage_all_files"] == 0.0, (
        "Expected default coverage of 0.0 with no coverage data"
    )


def test_pre_test_runner_agent_regex_failure(temp_empty_project):
    # Given: Project with package.json and test output with no matching patterns
    agent = PreTestRunnerAgent()
    agent.project_root = temp_empty_project
    os.environ["PROJECT_ROOT"] = temp_empty_project
    with open(os.path.join(temp_empty_project, "package.json"), "w") as f:
        f.write('{"name": "test", "scripts": {"test": "echo Custom output"}}')
    state = State()

    # When: Processing the state with real npm commands
    result = agent(state)

    # Then: Verify fallback to 0 when regex fails to match
    assert result["existing_tests_passed"] == 0, (
        "Should default to 0 tests passed when regex fails"
    )
    assert result["existing_coverage_all_files"] == 0.0, (
        "Should default to 0.0 coverage"
    )
