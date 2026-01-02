"""
Integration tests specifically for Phase 3 error recovery: ErrorRecoveryAgent, circuit breakers,
fallback strategies. Uses real deterministic implementations with existing fixtures.
"""

import pytest
import time

from src.error_recovery_agent import ErrorRecoveryAgent, RecoveryStrategy, AgentType
from src.circuit_breaker import (
    get_circuit_breaker,
    get_health_monitor,
    CircuitBreakerOpenException,
    CircuitBreakerState
)
from src.state import State


@pytest.mark.integration
class TestPhase3ErrorRecoveryIntegration:

    def test_standalone_recovery(self, dummy_state):
        """Test standalone ErrorRecoveryAgent recovery (simulate error, assert recovery action)."""
        agent = ErrorRecoveryAgent()
        
        # Register healthy services for deterministic retry success
        health_monitor = get_health_monitor()
        health_monitor.register_service("ollama_code", lambda: True)
        health_monitor.register_service("typescript_compiler", lambda: True)
        
        # Prepare failed state as dict (State TypedDict)
        failed_state: State = dict(dummy_state.__dict__)
        failed_state["failed_agent"] = AgentType.CODE_GENERATOR.value
        failed_state["error_context"] = {"service": "ollama_code"}
        failed_state["original_error"] = Exception("LLMError")  # Triggers recovery strategies
        
        # Execute recovery process
        recovered_state = agent.process(failed_state)
        
        # Assert recovery was applied successfully (deterministic: healthy services -> retry success)
        assert recovered_state.get("recovery_applied") is True
        details = recovered_state["recovery_details"]
        assert details["success"] is True
        assert details["strategy"] == RecoveryStrategy.RETRY.value
        assert details["attempts"] == 1

    def test_circuit_breaker_states(self):
        """Test CB states: CLOSED -> OPEN -> HALF-OPEN -> CLOSED with controlled failures."""
        # Low threshold/short timeout for fast test
        cb = get_circuit_breaker("test_cb", failure_threshold=2, recovery_timeout=1)
        
        def failing_func():
            raise Exception("Controlled failure")
        
        def success_func():
            return {"recovered": True}
        
        # CLOSED: 1st failure (still CLOSED)
        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 1
        
        # 2nd failure -> OPEN
        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 2
        assert cb.next_attempt_time is not None
        
        # Wait recovery timeout + margin
        time.sleep(1.2)
        
        # Post-timeout call -> HALF-OPEN, success -> CLOSED
        result = cb.call(success_func)
        assert result == {"recovered": True}
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.next_attempt_time is None

    def test_error_recovery_workflow_integration(self, dummy_state):
        """Test ErrorRecoveryAgent circuit breaker integration (simulates workflow recovery)."""
        agent = ErrorRecoveryAgent()
        cb = agent.circuit_breaker  # error_recovery CB
        cb.failure_threshold = 2
        cb.recovery_timeout = 1
    
        failed_state: State = dict(dummy_state.__dict__)
        failed_state["failed_agent"] = AgentType.CODE_GENERATOR.value
        error = Exception("Workflow agent failure")
        
        # Normal: CLOSED, recover succeeds
        recovered = agent.recover(failed_state, error)
        assert recovered.get("recovery_applied") is True
        
        # Force OPEN: fail threshold times via direct CB.call (simulates repeated recovery fails)
        def failing_recovery():
            raise Exception("Recovery failure")
        threshold = cb.failure_threshold
        for _ in range(threshold):
            with pytest.raises(Exception):
                cb.call(failing_recovery)
        assert cb.state == CircuitBreakerState.OPEN
        
        # OPEN: recover raises CircuitBreakerOpenException (protects workflow)
        with pytest.raises(CircuitBreakerOpenException):
            agent.recover(failed_state, error)
        
        # Wait timeout, success resets
        time.sleep(cb.recovery_timeout + 0.2)
        recovered2 = agent.recover(failed_state, error)
        assert recovered2.get("recovery_applied") is True
        assert cb.state == CircuitBreakerState.CLOSED