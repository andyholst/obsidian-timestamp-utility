import pytest
import os
from unittest.mock import Mock
from src.post_test_runner_agent import PostTestRunnerAgent
from src.state import State

# Path to the real project directory mounted in the test environment
REAL_PROJECT_ROOT = '/project'

def test_post_test_runner_agent_success():
    """
    Test that PostTestRunnerAgent successfully runs npm install and npm test
    in the real /project directory, which is mounted in the test environment.
    Assumes /project contains a valid Node.js project with package.json and tests.
    """
    # Given: A PostTestRunnerAgent instance using the real /project directory
    mock_llm = Mock()
    agent = PostTestRunnerAgent(mock_llm)
    agent.project_root = REAL_PROJECT_ROOT  # Use the real /project directory
    state = State()
    # Simulate pre-test results
    state['existing_tests_passed'] = 58
    state['existing_coverage_all_files'] = 52.44

    # When: Processing the state with real npm commands
    result = agent(state)

    # Then: Verify post-integration test metrics and improvements
    assert "post_integration_tests_passed" in result, "Post-integration tests passed missing from result"
    assert "post_integration_coverage_all_files" in result, "Post-integration coverage missing from result"
    assert "coverage_improvement" in result, "Coverage improvement metric missing"
    assert "tests_improvement" in result, "Tests improvement metric missing"

    # Verify post-integration metrics are at least as good as pre-integration
    assert result["post_integration_tests_passed"] >= result["existing_tests_passed"], "Tests should not decrease"
    assert result["post_integration_coverage_all_files"] >= result["existing_coverage_all_files"], "Coverage should not decrease"
    assert result["coverage_improvement"] >= 0, "Coverage improvement should be non-negative"
    assert result["tests_improvement"] >= 0, "Tests improvement should be non-negative"

def test_strip_ansi_codes():
    """
    Test the utility function to strip ANSI codes from text.
    This test does not involve npm commands and remains unchanged.
    """
    # Given: Text with and without ANSI codes
    mock_llm = Mock()
    agent = PostTestRunnerAgent(mock_llm)
    text_with_ansi = "\033[31mRed text\033[0m"
    plain_text = "Plain text"

    # When: Stripping ANSI codes
    result = agent.strip_ansi_codes(text_with_ansi)
    plain_result = agent.strip_ansi_codes(plain_text)

    # Then: Verify stripped output
    assert result == "Red text", "Expected ANSI codes to be removed"
    assert plain_result == "Plain text", "Expected plain text to remain unchanged"