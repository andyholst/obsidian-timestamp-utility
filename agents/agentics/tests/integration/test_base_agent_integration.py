import pytest
import time
from typing import Dict, Any
from src.base_agent import BaseAgent
from src.circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException
from src.monitoring import structured_log

@pytest.mark.integration
class TestBaseAgentIntegration:

    def test_scenario1_basic_resilience_monitoring(self, caplog):
        """Scenario 1: Real BaseAgent subclass; invoke; assert monitoring logs."""
        class TestAgent(BaseAgent):
            def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
                state['agent_processed'] = True
                return state

        agent = TestAgent("basic_test_agent")
        initial_state = {}

        result = agent.invoke(initial_state)

        assert result['agent_processed'] is True

        # Assert structured monitoring logs emitted
        records = [r for r in caplog.records if "basic_test_agent" in r.message]
        assert len(records) >= 2
        assert any("agent_start" in r.message for r in records)
        assert any("agent_complete" in r.message for r in records)

    def test_scenario2_force_failures_circuit_open(self):
        """Scenario 2: Force 3x failures; assert circuit breaker opens."""
        class FailingAgent(BaseAgent):
            def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
                raise ValueError("forced failure")

        agent = FailingAgent("failing_agent")

        state = {}

        # Fail threshold times (default 3 for code_generator)
        for i in range(3):
            with pytest.raises(ValueError):
                agent.invoke(state)

        # Check failure count
        cb = get_circuit_breaker("failing_agent")
        assert cb.failure_count == 3

        # 4th invoke should still fail ValueError (not yet open? wait, after 3rd failure, on 3rd _record_failure if >=threshold open
        # From code: after failure_count >= threshold in _record_failure
        # So after 3rd fail, open.
        with pytest.raises(CircuitBreakerOpenException):
            agent.invoke(state)

        assert cb.state.name == "OPEN"

    def test_scenario3_recovery_timeout_reset(self):
        """Scenario 3: Recovery timeout; assert resets after timeout."""
        class RecoverConfigAgent(BaseAgent):
            def _get_circuit_breaker_config(self) -> Dict[str, Any]:
                return {"failure_threshold": 1, "recovery_timeout": 2}  # Short for test

            def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
                raise ValueError("recover fail")  # Fail first

        class SuccessAgent(BaseAgent):
            def _get_circuit_breaker_config(self) -> Dict[str, Any]:
                return {"failure_threshold": 1, "recovery_timeout": 2}

            def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
                state['recovered'] = True
                return state

        name = "recovery_agent"

        # Fail once to open (threshold 1)
        fail_agent = RecoverConfigAgent(name)
        state = {}
        with pytest.raises(ValueError):
            fail_agent.invoke(state)

        cb = get_circuit_breaker(name)
        assert cb.state.name == "OPEN"
        assert cb.next_attempt_time is not None

        # Sleep past recovery timeout
        time.sleep(3)

        # Now success should reset
        success_agent = SuccessAgent(name)
        result = success_agent.invoke(state)
        assert result['recovered'] is True

        # Verify reset
        cb = get_circuit_breaker(name)
        assert cb.state.name == "CLOSED"
        assert cb.failure_count == 0

    def test_scenario4_structured_logging_json(self, caplog):
        """Scenario 4: Structured logging integration; assert JSON logs emitted."""
        class LoggingAgent(BaseAgent):
            def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
                self.monitor.info("custom_agent_event", {"step": "processing"})
                state['logged'] = True
                return state

        agent = LoggingAgent("logging_agent")
        state = {}

        result = agent.invoke(state)

        assert result['logged'] is True

        # Assert JSON structured logs
        json_logs = [r for r in caplog.records if r.message.startswith('{')]
        assert len(json_logs) >= 3  # start, custom, complete

        # Parse one JSON log
        custom_log = next((r for r in json_logs if '"custom_agent_event"' in r.message), None)
        assert custom_log is not None
        import json
        log_data = json.loads(custom_log.message)
        assert log_data["event"] == "custom_agent_event"
        assert "step" in log_data