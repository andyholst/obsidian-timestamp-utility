import pytest
from src.output_result_agent import OutputResultAgent
from src.state import State
import logging

def test_output_result_agent(caplog):
    # Given: A state with a result
    agent = OutputResultAgent()
    state = State(result={"title": "Test", "description": "Desc"})
    
    # When: Processing the state
    with caplog.at_level(logging.INFO):
        result = agent(state)
    
    # Then: Verify result is logged
    assert "Final result:" in caplog.text, "Expected log message"
    assert '"title": "Test"' in caplog.text, "Expected title in log"
    assert result == state, "State should be unchanged"

def test_output_result_agent_empty_result(caplog):
    # Given: A state with an empty result
    agent = OutputResultAgent()
    state = State(result={})
    
    # When: Processing the state
    with caplog.at_level(logging.INFO):
        result = agent(state)
    
    # Then: Verify empty result is logged
    assert "Final result:" in caplog.text, "Expected log message"
    assert "{}" in caplog.text, "Expected empty JSON in log"
    assert result == state, "State should be unchanged"
