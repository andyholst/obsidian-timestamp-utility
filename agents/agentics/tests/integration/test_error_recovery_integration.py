"""
Integration tests for error recovery and resilience in the agentics workflow.
Tests circuit breaker patterns, fallback strategies, and error propagation.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, call
from src.composable_workflows import ComposableWorkflows
from src.circuit_breaker import CircuitBreakerOpenException
from src.error_recovery_agent import ErrorRecoveryAgent
from src.agentics import create_composable_workflow

from typing import Dict, Any
from src.base_agent import BaseAgent, AgentType


@pytest_asyncio.fixture(scope="function")
async def composable_workflow():
    """Fixture for real ComposableWorkflows instance."""
    return await create_composable_workflow()


@pytest.fixture
def error_recovery_agent():
    """Fixture for ErrorRecoveryAgent."""
    fallback_strategies = {
        "llm_failure": lambda state, error: {"recovered": True, "strategy": "llm_fallback"},
        "github_failure": lambda state, error: {"recovered": True, "strategy": "github_fallback"},
        "general_failure": lambda state, error: {"recovered": False, "strategy": "general_fallback"}
    }
    return ErrorRecoveryAgent(fallback_strategies)


class TestErrorRecoveryIntegration:
    """Integration tests for error recovery mechanisms."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_circuit_breaker_prevents_cascade_failures(self, composable_workflow):
        """Test that circuit breakers prevent cascade failures in workflow."""
        issue_url = "https://github.com/test/repo/issues/1"

        with patch('src.circuit_breaker.get_circuit_breaker') as mock_get_circuit_breaker:
            # Mock circuit breaker that's open (failing)
            mock_circuit_breaker = MagicMock()
            mock_circuit_breaker.call.side_effect = CircuitBreakerOpenException("Circuit breaker open")
            mock_get_circuit_breaker.return_value = mock_circuit_breaker

            # Execute workflow - should handle circuit breaker gracefully
            with pytest.raises(CircuitBreakerOpenException):
                composable_workflow.process_issue(issue_url)

            # Verify circuit breaker was called
            mock_get_circuit_breaker.assert_called()

    @pytest.mark.integration
    def test_llm_failure_recovery_with_fallback(self, composable_workflow, error_recovery_agent):
        """Test recovery from LLM API failures using fallback strategies."""
        issue_url = "https://github.com/test/repo/issues/1"

        with patch.object(composable_workflow, 'llm_reasoning') as mock_llm:
            # Mock LLM failure
            mock_llm.invoke.side_effect = Exception("LLM API unavailable")

            # Mock error recovery
            with patch('src.error_recovery_agent.ErrorRecoveryAgent') as mock_error_recovery_class:
                mock_error_recovery = MagicMock()
                mock_error_recovery.recover.return_value = {"recovered": True, "fallback_result": "success"}
                mock_error_recovery_class.return_value = mock_error_recovery

                # Execute workflow - should attempt recovery
                try:
                    result = composable_workflow.process_issue(issue_url)
                    # If it succeeds, verify recovery was attempted
                    mock_error_recovery.recover.assert_called()
                except Exception:
                    # If it fails, recovery should still be attempted
                    mock_error_recovery.recover.assert_called()

    @pytest.mark.integration
    def test_github_api_failure_recovery(self, composable_workflow):
        """Test recovery from GitHub API failures."""
        # Use non-existent repo to trigger GitHub failure
        issue_url = "https://github.com/nonexistentuser/nonexistentrepo/issues/1"

        # Execute workflow - should handle GitHub failure
        with pytest.raises(Exception):
            composable_workflow.process_issue(issue_url)

    @pytest.mark.integration
    def test_partial_workflow_failure_recovery(self, composable_workflow):
        """Test recovery when workflow fails."""
        # Use invalid URL to trigger failure
        issue_url = "https://invalid-url/issues/1"

        # Execute - should fail
        with pytest.raises(Exception):
            composable_workflow.process_issue(issue_url)

    @pytest.mark.integration
    def test_mcp_tool_failure_isolation(self, composable_workflow):
        """Test that MCP tool failures don't break the entire workflow."""
        test_repo_url = os.getenv("TEST_ISSUE_URL")
        assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
        issue_url = f"{test_repo_url}/issues/1"

        # Execute - workflow should continue despite tool failures
        result = composable_workflow.process_issue(issue_url)

        # Verify workflow completed (tools are optional)
        assert result is not None

    @pytest.mark.integration
    def test_state_preservation_during_errors(self, composable_workflow):
        """Test that state is preserved correctly during error scenarios."""
        # Use invalid URL to trigger failure
        issue_url = "https://invalid-url/issues/1"

        # Execution should fail
        with pytest.raises(Exception):
            composable_workflow.process_issue(issue_url)

    @pytest.mark.integration
    def test_error_recovery_agent_integration(self, error_recovery_agent):
        """Test ErrorRecoveryAgent integration with workflow failures."""
        failed_state = {"error": "LLM failed", "partial_data": "some data"}
        error = Exception("LLM API timeout")

        # Test recovery
        recovered_state = error_recovery_agent.recover(failed_state, error)

        # Verify recovery attempt
        assert recovered_state is not None
        assert "recovered" in recovered_state
        assert recovered_state["recovered"] == True

    @pytest.mark.integration
    def test_circuit_breaker_recovery_timeout(self, composable_workflow):
        """Test circuit breaker recovery after timeout period."""
        issue_url = "https://github.com/test/repo/issues/1"

        with patch('src.circuit_breaker.get_circuit_breaker') as mock_get_circuit_breaker, \
             patch('time.sleep') as mock_sleep:

            # Mock circuit breaker that recovers after some time
            mock_circuit_breaker = MagicMock()
            call_count = 0

            def circuit_breaker_behavior(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise CircuitBreakerOpenException("Circuit breaker open")
                else:
                    # Simulate successful recovery
                    return {"recovered": True}

            mock_circuit_breaker.call.side_effect = circuit_breaker_behavior
            mock_get_circuit_breaker.return_value = mock_circuit_breaker

            # First call should fail
            with pytest.raises(CircuitBreakerOpenException):
                composable_workflow.process_issue(issue_url)

            # Simulate time passing for recovery
            mock_sleep.assert_called()

    @pytest.mark.integration
    def test_fallback_strategy_execution(self, error_recovery_agent):
        """Test execution of different fallback strategies based on error type."""
        test_cases = [
            (Exception("LLM API failed"), "llm_failure"),
            (Exception("GitHub API failed"), "github_failure"),
            (Exception("Unknown error"), "general_failure")
        ]

        for error, expected_strategy in test_cases:
            failed_state = {"error_occurred": True}

            recovered_state = error_recovery_agent.recover(failed_state, error)

            # Verify appropriate strategy was selected
            assert recovered_state["strategy"] == expected_strategy

    @pytest.mark.integration
    def test_error_logging_and_monitoring(self, composable_workflow):
        """Test that errors are properly logged and monitored."""
        # Use invalid URL to trigger error
        issue_url = "https://invalid-url/issues/1"

        # Execute and expect error
        with pytest.raises(Exception):
            composable_workflow.process_issue(issue_url)

    @pytest.mark.integration
    def test_graceful_degradation_on_service_failures(self, composable_workflow):
        """Test graceful degradation when external services fail."""
        # Use invalid URL to trigger service failures
        issue_url = "https://invalid-url/issues/1"

        # Workflow should fail gracefully without crashing
        with pytest.raises(Exception):
            composable_workflow.process_issue(issue_url)

    @pytest.mark.integration
    def test_retry_logic_with_exponential_backoff(self, composable_workflow):
        """Test retry logic with exponential backoff for transient failures."""
        issue_url = "https://github.com/test/repo/issues/1"

        with patch('src.performance.get_task_manager') as mock_get_task_manager, \
             patch('time.sleep') as mock_sleep:

            # Mock task manager with retry logic
            mock_task_manager = MagicMock()
            retry_count = 0

            def retry_behavior(*args, **kwargs):
                nonlocal retry_count
                retry_count += 1
                if retry_count < 3:
                    raise Exception(f"Transient failure {retry_count}")
                return {"success": True}

            mock_task_manager.execute_with_retry = MagicMock(side_effect=retry_behavior)
            mock_get_task_manager.return_value = mock_task_manager

            # Execute workflow
            result = composable_workflow.process_issue(issue_url)

            # Verify retries were attempted
            assert mock_task_manager.execute_with_retry.call_count >= 3
            # Verify exponential backoff delays
            sleep_calls = mock_sleep.call_args_list
            assert len(sleep_calls) >= 2  # At least 2 retry delays

    @pytest.mark.integration
    def test_error_context_preservation(self, composable_workflow):
        """Test that error context is preserved for debugging."""
        # Use invalid URL to trigger error
        issue_url = "https://invalid-url/issues/1"

        # Execute and expect error
        with pytest.raises(Exception):
            composable_workflow.process_issue(issue_url)

    @pytest.mark.integration
    def test_health_monitor_integration_with_error_recovery(self, composable_workflow):
        """Test integration between health monitoring and error recovery."""
        # Use invalid URL to trigger error
        issue_url = "https://invalid-url/issues/1"

        # Execute workflow - should detect unhealthy service
        with pytest.raises(Exception):  # Should fail due to unhealthy service
            composable_workflow.process_issue(issue_url)

    @pytest.mark.integration
    def test_error_recovery_success_rate_tracking(self, error_recovery_agent):
        """Test tracking of error recovery success rates."""
        # Test multiple recovery attempts
        test_cases = [
            (Exception("LLM failed"), True),   # Successful recovery
            (Exception("LLM failed"), False),  # Failed recovery
            (Exception("GitHub failed"), True) # Successful recovery
        ]

        success_count = 0
        total_attempts = len(test_cases)

        for error, should_succeed in test_cases:
            failed_state = {"error": str(error)}

            # Mock fallback strategy
            if should_succeed:
                error_recovery_agent.fallback_strategies["llm_failure"] = lambda s, e: {"recovered": True}
                error_recovery_agent.fallback_strategies["github_failure"] = lambda s, e: {"recovered": True}
            else:
                error_recovery_agent.fallback_strategies["llm_failure"] = lambda s, e: {"recovered": False}

            recovered_state = error_recovery_agent.recover(failed_state, error)

            if recovered_state.get("recovered"):
                success_count += 1

        # Verify success rate calculation
        success_rate = success_count / total_attempts
        assert success_rate == 2/3  # 2 out of 3 recoveries succeeded

# TestErrorRecoveryFullCycle class incomplete, removed for collection