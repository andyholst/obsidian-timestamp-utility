import pytest
import os
from unittest.mock import Mock
from src.post_test_runner_agent import PostTestRunnerAgent
from src.state import State
from _e2e_helpers import make_seeded_project_root, plugin_ts_tests_present

# Seed an ISOLATED temp PROJECT_ROOT with the real plugin files so the pipeline's
# jest phase operates against a valid baseline (jest must find the existing
# src/__tests__/main.test.ts). Using a seeded temp dir (not the raw env PROJECT_ROOT,
# which may have been repointed to an empty temp dir by a sibling test module) keeps
# this test hermetic and avoids "test count did not grow" (TestRecoveryNeeded).
REAL_PROJECT_ROOT = make_seeded_project_root(prefix="post_test_project_")
# The plugin's TypeScript jest scaffold is required here; in the integration container
# it is shadowed by the Python source mount at /app/src and /project is not mounted, so
# it is absent -> skip cleanly (B17: live tests skip cleanly).
HAS_TS_TESTS = plugin_ts_tests_present(REAL_PROJECT_ROOT)


@pytest.mark.skipif(
    not HAS_TS_TESTS,
    reason="plugin TypeScript test scaffold (src/__tests__/main.test.ts) not "
    "mounted in integration container (shadowed by Python src mount)",
)
def test_post_test_runner_agent_success(dummy_llm):
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
    state["existing_tests_passed"] = 58
    state["existing_coverage_all_files"] = 52.44

    # When: Processing the state with real npm commands
    result = agent(state)

    # Then: Verify post-integration test metrics and improvements
    assert "post_integration_tests_passed" in result, (
        "Post-integration tests passed missing from result"
    )
    assert "post_integration_coverage_all_files" in result, (
        "Post-integration coverage missing from result"
    )
    assert "coverage_improvement" in result, "Coverage improvement metric missing"
    assert "tests_improvement" in result, "Tests improvement metric missing"

    # Verify post-integration metrics are present
    assert result["post_integration_tests_passed"] >= 0, (
        "Post-integration tests passed should be non-negative"
    )
    assert result["post_integration_coverage_all_files"] >= 0, (
        "Post-integration coverage should be non-negative"
    )


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
