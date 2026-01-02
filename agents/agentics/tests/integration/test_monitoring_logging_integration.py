"""
Integration tests for monitoring and structured logging in Agentics.
Verifies structured_log emits correct JSON-formatted events/levels via pytest caplog.
Covers basic events, workflow simulation, error logging, parallel exec logging.
"""

import pytest
import json
import time
from src.monitoring import structured_log
from src.state import CodeGenerationState


class TestMonitoringLoggingIntegration:
    """Integration tests for structured logging and observability."""

    @pytest.mark.integration
    def test_structured_log_basic_events(self, caplog):
        """Test basic structured log events with different levels."""
        caplog.set_level("INFO")
        monitor = structured_log("test_agent")

        # Info event
        monitor.info("agent_executed", {
            "agent": "code_generator",
            "status": "success",
            "input_size": 42,
            "output_tokens": 150
        })

        # Warning event
        monitor.warning("agent_retry", {
            "agent": "code_generator",
            "attempt": 2,
            "reason": "llm_timeout"
        })

        # Error event
        monitor.error("agent_failed", {
            "agent": "code_integrator",
            "step": "integration"
        }, error=ValueError("Code validation failed"))

        records = caplog.records
        assert len(records) == 3

        # Verify info record
        log1 = json.loads(records[0].message)
        assert log1["level"] == "INFO"
        assert log1["event"] == "agent_executed"
        assert log1["component"] == "test_agent"
        assert log1["agent"] == "code_generator"
        assert log1["status"] == "success"
        assert log1["input_size"] == 42

        # Verify warning record
        log2 = json.loads(records[1].message)
        assert log2["level"] == "WARNING"
        assert log2["event"] == "agent_retry"
        assert log2["attempt"] == 2

        # Verify error record
        log3 = json.loads(records[2].message)
        assert log3["level"] == "ERROR"
        assert log3["event"] == "agent_failed"
        assert log3["error"]["type"] == "ValueError"
        assert "Code validation failed" in log3["error"]["message"]

    @pytest.mark.integration
    def test_structured_log_parallel_execution_logging(self, caplog, dummy_state):
        """Test logging during simulated parallel agent execution."""
        caplog.set_level("INFO")
        monitor = structured_log("test_parallel_workflow")

        # Simulate parallel start
        monitor.info("parallel_agents_started", {
            "num_agents": 2,
            "agents": ["agent1", "agent2"],
            "state_size": len(str(dummy_state))
        })

        # Simulate completion
        monitor.info("parallel_agents_executed", {
            "num_agents": 2,
            "success_count": 2,
            "total_duration": 0.85,
            "throughput": "2.35 agents/s"
        })

        records = caplog.records
        assert len(records) == 2

        log1 = json.loads(records[0].message)
        assert log1["event"] == "parallel_agents_started"
        assert log1["num_agents"] == 2

        log2 = json.loads(records[1].message)
        assert log2["event"] == "parallel_agents_executed"
        assert log2["success_count"] == 2

    @pytest.mark.integration
    def test_structured_log_workflow_progress(self, caplog):
        """Test workflow progress logging with timestamps."""
        caplog.set_level("INFO")
        monitor = structured_log("test_workflow")

        start_time = time.time()
        monitor.info("workflow_started", {"phase": "composable_workflows", "issue_id": "123"})

        time.sleep(0.1)  # Simulate work

        monitor.info("workflow_phase_completed", {
            "phase": "issue_processing",
            "duration": 0.45,
            "next_phase": "code_generation"
        })

        end_time = time.time()
        monitor.info("workflow_completed", {
            "total_duration": end_time - start_time,
            "phases_completed": 3,
            "success": True
        })

        records = caplog.records
        assert len(records) == 3

        events = [json.loads(r.message)["event"] for r in records]
        assert events == [
            "workflow_started",
            "workflow_phase_completed",
            "workflow_completed"
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])