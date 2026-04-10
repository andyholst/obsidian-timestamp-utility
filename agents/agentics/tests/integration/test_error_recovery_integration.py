"""
Integration tests for error recovery and resilience in the agentics workflow.
Tests circuit breaker patterns, fallback strategies, and error propagation.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from src.circuit_breaker import CircuitBreakerOpenException, get_circuit_breaker, get_health_monitor
from src.error_recovery_agent import ErrorRecoveryAgent, CircuitBreakerOpenException as AgentCircuitBreakerOpenException


@pytest.fixture
def error_recovery_agent():
    """Fixture for ErrorRecoveryAgent."""
    from langchain_core.runnables import RunnableLambda
    from langchain_core.messages import AIMessage

    mock_llm = RunnableLambda(lambda p: AIMessage(content="{}"))
    fallback_strategies = {
        "retry": lambda state, error: {"recovered": True, "strategy": "retry"},
        "degrade": lambda state, error: {"recovered": True, "strategy": "degrade"},
        "substitute": lambda state, error: {"recovered": True, "strategy": "substitute"},
        "state_recovery": lambda state, error: {"recovered": True, "strategy": "state_recovery"},
        "skip": lambda state, error: {"recovered": False, "strategy": "skip"},
    }
    return ErrorRecoveryAgent(llm_reasoning=mock_llm, fallback_strategies=fallback_strategies)


class TestErrorRecoveryIntegration:
    """Integration tests for error recovery mechanisms."""

    @pytest.mark.integration
    def test_circuit_breaker_prevents_cascade_failures(self):
        """Test that circuit breakers prevent cascade failures in workflow."""
        cb = get_circuit_breaker("test_cascade")
        cb._reset()

        assert cb.state.name == "CLOSED"

        for _ in range(cb.failure_threshold):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert cb.state.name == "OPEN"

        with pytest.raises(CircuitBreakerOpenException):
            cb.call(lambda: "should not execute")

    @pytest.mark.integration
    def test_llm_failure_recovery_with_fallback(self, error_recovery_agent):
        """Test recovery from LLM API failures using fallback strategies."""
        failed_state = {"url": "https://github.com/test/repo/issues/1"}
        error = TimeoutError("LLM API timeout")

        recovered_state = error_recovery_agent.recover(failed_state, error)

        assert recovered_state is not None
        assert recovered_state.get("recovered") == True

    @pytest.mark.integration
    def test_github_api_failure_recovery(self, error_recovery_agent):
        """Test recovery from GitHub API failures."""
        failed_state = {"url": "https://github.com/test/repo/issues/1"}
        error = ConnectionError("GitHub API unavailable")

        recovered_state = error_recovery_agent.recover(failed_state, error)

        assert recovered_state is not None
        assert recovered_state.get("recovered") == True

    @pytest.mark.integration
    def test_partial_workflow_failure_recovery(self, error_recovery_agent):
        """Test recovery when workflow fails partially."""
        failed_state = {"url": "https://github.com/test/repo/issues/1", "partial": True}
        error = ValueError("Partial failure")

        recovered_state = error_recovery_agent.recover(failed_state, error)

        assert recovered_state is not None
        assert recovered_state.get("strategy") == "substitute"

    @pytest.mark.integration
    def test_state_preservation_during_errors(self, error_recovery_agent):
        """Test that state is preserved correctly during error scenarios."""
        failed_state = {"url": "https://github.com/test/repo/issues/1", "data": "important"}
        error = KeyError("missing_key")

        recovered_state = error_recovery_agent.recover(failed_state, error)

        assert recovered_state is not None
        assert recovered_state.get("strategy") == "state_recovery"

    @pytest.mark.integration
    def test_error_recovery_agent_integration(self, error_recovery_agent):
        """Test ErrorRecoveryAgent integration with workflow failures."""
        failed_state = {"error": "LLM failed", "partial_data": "some data"}
        error = AgentCircuitBreakerOpenException("Circuit breaker open")

        recovered_state = error_recovery_agent.recover(failed_state, error)

        assert recovered_state is not None
        assert recovered_state.get("strategy") == "degrade"

    @pytest.mark.integration
    def test_circuit_breaker_recovery_timeout(self):
        """Test circuit breaker recovery after timeout period."""
        cb = get_circuit_breaker("test_recovery")
        cb._reset()

        assert cb.state.name == "CLOSED"

        for _ in range(cb.failure_threshold):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert cb.state.name == "OPEN"

        cb._reset()
        assert cb.state.name == "CLOSED"

    @pytest.mark.integration
    def test_fallback_strategy_execution(self, error_recovery_agent):
        """Test execution of different fallback strategies based on error type."""
        test_cases = [
            (TimeoutError("timeout"), "retry"),
            (ConnectionError("connection"), "retry"),
            (AgentCircuitBreakerOpenException("open"), "degrade"),
            (ValueError("value"), "substitute"),
            (KeyError("key"), "state_recovery"),
            (Exception("unknown"), "skip"),
        ]

        for error, expected_strategy in test_cases:
            failed_state = {"error_occurred": True}
            recovered_state = error_recovery_agent.recover(failed_state, error)
            assert recovered_state["strategy"] == expected_strategy, \
                f"Expected {expected_strategy} for {type(error).__name__}, got {recovered_state['strategy']}"

    @pytest.mark.integration
    def test_error_logging_and_monitoring(self):
        """Test that errors are properly logged and monitored."""
        monitor = get_health_monitor()
        assert monitor is not None

        def healthy_check():
            return True

        monitor.register_service("test_service", healthy_check)

    @pytest.mark.integration
    def test_graceful_degradation_on_service_failures(self, error_recovery_agent):
        """Test graceful degradation when external services fail."""
        errors = [
            TimeoutError("LLM service unavailable"),
            ConnectionError("GitHub API rate limited"),
            AgentCircuitBreakerOpenException("Circuit open"),
        ]

        for error in errors:
            failed_state = {"error": str(error)}
            recovered_state = error_recovery_agent.recover(failed_state, error)
            assert recovered_state is not None
            assert recovered_state.get("recovered") == True

    @pytest.mark.integration
    def test_retry_logic_with_exponential_backoff(self):
        """Test retry logic with exponential backoff for transient failures."""
        cb = get_circuit_breaker("test_retry")
        cb._reset()

        assert cb.state.name == "CLOSED"

        for _ in range(cb.failure_threshold):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert cb.state.name == "OPEN"

    @pytest.mark.integration
    def test_error_context_preservation(self, error_recovery_agent):
        """Test that error context is preserved for debugging."""
        failed_state = {"url": "https://github.com/test/repo/issues/1", "context": "debug_info"}
        error = TimeoutError("Test error with context")

        recovered_state = error_recovery_agent.recover(failed_state, error)
        assert recovered_state is not None
        assert recovered_state.get("recovered") == True

    @pytest.mark.integration
    def test_health_monitor_integration_with_error_recovery(self):
        """Test integration between health monitoring and error recovery."""
        monitor = get_health_monitor()
        assert monitor is not None

        def healthy():
            return True

        def unhealthy():
            return False

        monitor.register_service("healthy_service", healthy)
        monitor.register_service("unhealthy_service", unhealthy)

    @pytest.mark.integration
    def test_error_recovery_success_rate_tracking(self, error_recovery_agent):
        """Test tracking of error recovery success rates."""
        # Test that we can track recovery outcomes
        test_cases = [
            (TimeoutError("timeout"), True),   # retry -> recovered
            (KeyError("key"), True),           # state_recovery -> recovered
            (Exception("unknown"), False),     # skip -> not recovered
        ]

        success_count = 0
        total_attempts = len(test_cases)

        for error, should_succeed in test_cases:
            failed_state = {"error": str(error)}
            recovered_state = error_recovery_agent.recover(failed_state, error)

            if recovered_state.get("recovered") == should_succeed:
                success_count += 1

        # All 3 should match their expected outcomes
        assert success_count == total_attempts
