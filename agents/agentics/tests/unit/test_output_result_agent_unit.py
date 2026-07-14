import pytest
from src.output_result_agent import OutputResultAgent
from src.state import State
import logging
import json


def test_output_result_agent(caplog):
    # Given: A state with a result
    agent = OutputResultAgent()
    agent.logger.setLevel(
        logging.DEBUG
    )  # Set logger level to DEBUG to capture log_info messages
    state = State(result={"title": "Test", "description": "Desc"})

    # When: Processing the state
    with caplog.at_level(logging.DEBUG):  # Capture logs at DEBUG level
        result = agent(state)

    # Then: Verify result is logged and the honest self-correct fields are surfaced
    # (recovery_attempt=0 < MAX_SELF_CORRECT_ATTEMPTS => success=True, failing_gate="").
    assert (
        "Final result content: " + json.dumps(state["result"], indent=2) in caplog.text
    ), "Expected result content in log"
    assert result["self_correct_success"] is True
    assert result["failing_gate"] == ""
    assert result["result"] == state["result"]


def test_output_result_agent_empty_result(caplog):
    # Given: A state with an empty result
    agent = OutputResultAgent()
    agent.logger.setLevel(
        logging.DEBUG
    )  # Set logger level to DEBUG to capture log_info messages
    state = State(result={})

    # When: Processing the state
    with caplog.at_level(logging.DEBUG):
        result = agent(state)

    # Then: Verify empty result is logged
    assert "Final result content: {}" in caplog.text, "Expected empty JSON in log"
    assert result["self_correct_success"] is True
    assert result["failing_gate"] == ""
    assert result["result"] == {}
