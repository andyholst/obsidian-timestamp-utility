import pytest
import os
from src.pre_test_runner_agent import PreTestRunnerAgent
from src.state import State

# Path to the real project directory mounted in the test environment
REAL_PROJECT_ROOT = '/project'

@pytest.fixture
def temp_empty_project(tmp_path):
    # Given: An empty temporary project directory without package.json
    project_dir = tmp_path / "empty_project"
    project_dir.mkdir()
    return str(project_dir)

def test_pre_test_runner_agent_success():
    """
    Test that PreTestRunnerAgent successfully runs npm install and npm test
    in the real /project directory, which is mounted in the test environment.
    Assumes /project contains a valid Node.js project with package.json and tests.
    """
    # Given: A PreTestRunnerAgent instance using the real /project directory
    agent = PreTestRunnerAgent()
    agent.project_root = REAL_PROJECT_ROOT  # Use the real /project directory
    os.environ['PROJECT_ROOT'] = REAL_PROJECT_ROOT
    state = State()

    # When: Processing the state with real npm commands
    result = agent(state)

    # Then: Verify test metrics match integration test expectations
    assert "existing_tests_passed" in result, "Number of passing tests missing from result"
    assert "existing_coverage_all_files" in result, "Coverage percentage missing from result"
    assert result["existing_tests_passed"] == 58, "Expected 58 tests to pass based on current test output"
    assert result["existing_coverage_all_files"] == 52.44, "Expected 52.44% line coverage based on current test output"

def test_pre_test_runner_agent_no_package_json(temp_empty_project):
    """
    Test that PreTestRunnerAgent raises a RuntimeError when package.json is missing.
    Uses a temporary empty directory to simulate this condition.
    """
    # Given: A PreTestRunnerAgent instance with an empty project directory
    agent = PreTestRunnerAgent()
    agent.project_root = temp_empty_project  # Temporary directory without package.json
    os.environ['PROJECT_ROOT'] = temp_empty_project
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
    os.environ['PROJECT_ROOT'] = '/project'
    text_with_ansi = "\033[31mRed text\033[0m"
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
    os.environ['PROJECT_ROOT'] = temp_empty_project
    agent.install_command = "echo Installing"
    agent.test_command = "echo 'Tests: 5 passed, 5 total'"
    state = State()
    
    # When: Processing the state with custom commands
    result = agent(state)
    
    # Then: Verify custom commands run successfully and output is parsed
    assert "existing_tests_passed" in result, "Should report tests passed"
    assert "existing_coverage_all_files" in result, "Should report coverage"
    assert result["existing_tests_passed"] == 5, "Expected 5 tests passed based on custom command output"
    assert result["existing_coverage_all_files"] == 0.0, "Expected default coverage of 0.0 with no coverage data"

def test_pre_test_runner_agent_regex_failure(temp_empty_project):
    # Given: Project with package.json and test output with no matching patterns
    agent = PreTestRunnerAgent()
    agent.project_root = temp_empty_project
    os.environ['PROJECT_ROOT'] = temp_empty_project
    with open(os.path.join(temp_empty_project, 'package.json'), 'w') as f:
        f.write('{"name": "test", "scripts": {"test": "echo Custom output"}}')
    state = State()
    
    # When: Processing the state with real npm commands
    result = agent(state)
    
    # Then: Verify fallback to 0 when regex fails to match
    assert result["existing_tests_passed"] == 0, "Should default to 0 tests passed when regex fails"
    assert result["existing_coverage_all_files"] == 0.0, "Should default to 0.0 coverage"
