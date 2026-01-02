import pytest
import time
import logging
from typing import Dict, Any

from src.base_agent import BaseAgent


@pytest.mark.integration
class TestBaseAgentIntegration:

    def test_circuit_breaker_standalone(self, dummy_state, real_ollama_config):
        """Scenario 9: CB standalone trip/reset - 3 failures -> OPEN, timeout + success -> CLOSED."""
        class FailingAgent(BaseAgent):
            def _get_circuit_breaker_config(self) -> Dict[str, Any]:
                return {"failure_threshold": 3, "recovery_timeout": 2}

            def process(self, state):
                raise ValueError("fail")

        agent = FailingAgent("cb_standalone")
        cb = agent.circuit_breaker

        for _ in range(3):
            with pytest.raises(ValueError):
                agent.invoke(dummy_state)

        assert cb.failure_count == 3
        assert cb.state.name == "OPEN"

        time.sleep(cb.recovery_timeout + 0.1)

        class SuccessAgent(BaseAgent):
            def _get_circuit_breaker_config(self) -> Dict[str, Any]:
                return {"failure_threshold": 3, "recovery_timeout": 2}

            def process(self, state):
                return state

        success_agent = SuccessAgent("cb_standalone")
        result = success_agent.invoke(dummy_state)

        assert cb.state.name == "CLOSED"
        assert cb.failure_count == 0

    def test_monitoring_logging(self, caplog, dummy_state, real_ollama_config):
        """Scenario 10: BaseAgent monitoring/logging - assert structured INFO logs emitted."""
        class TestAgent(BaseAgent):
            def process(self, state):
                return state

        agent = TestAgent("monitoring_test")
        caplog.set_level(logging.INFO)

        result = agent.invoke(dummy_state)

        records = caplog.records
        assert len(records) >= 2

        # Structured JSON logs
        structured_logs = [r for r in records if r.message.startswith('{')]
        assert len(structured_logs) >= 2

        # INFO level logs
        info_logs = [r for r in records if r.levelno == logging.INFO]
        assert len(info_logs) >= 2

        # Specific agent events
        assert any('"agent_start"' in r.message for r in records)
        assert any('"agent_complete"' in r.message for r in records)