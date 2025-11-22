import pytest
import logging
from unittest.mock import patch, MagicMock
from src.base_agent import BaseAgent
from src.state import State

class MockAgent(BaseAgent):
    def __init__(self, name: str):
        super().__init__(name)

    def process(self, state: State) -> State:
        # Mock implementation for testing
        state['mock_processed'] = True
        return state

def test_base_agent_init():
    # Given: A mock agent
    # When: Initializing the agent
    agent = MockAgent("TestAgent")

    # Then: Agent has correct name and logger
    assert agent.name == "TestAgent"
    assert isinstance(agent.logger, logging.Logger)
    assert agent.logger.name == "TestAgent"

def test_base_agent_call_success():
    # Given: A mock agent and initial state
    agent = MockAgent("TestAgent")
    state = State(url="", ticket_content="", refined_ticket={}, result={}, generated_code="", generated_tests="", existing_tests_passed=0, existing_coverage_all_files=0.0, relevant_code_files=[], relevant_test_files=[])

    # When: Calling the agent
    result = agent(state)

    # Then: State is processed and preserved
    assert result['mock_processed'] == True
    assert isinstance(result, dict)
    # Ensure all original keys are present
    for key in state.keys():
        assert key in result

def test_base_agent_call_exception():
    # Given: A failing agent that raises exception
    class FailingAgent(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name)

        def process(self, state: State) -> State:
            raise ValueError("Test error")

    agent = FailingAgent("FailingAgent")
    state = State(url="", ticket_content="", refined_ticket={}, result={}, generated_code="", generated_tests="", existing_tests_passed=0, existing_coverage_all_files=0.0, relevant_code_files=[], relevant_test_files=[])

    # When/Then: Calling the agent raises the exception
    with pytest.raises(ValueError, match="Test error"):
        agent(state)

def test_base_agent_process_not_implemented():
    # Given: BaseAgent instance
    agent = BaseAgent("BaseAgent")
    state = State(url="", ticket_content="", refined_ticket={}, result={}, generated_code="", generated_tests="", existing_tests_passed=0, existing_coverage_all_files=0.0, relevant_code_files=[], relevant_test_files=[])

    # When/Then: Calling process raises NotImplementedError
    with pytest.raises(NotImplementedError, match="Subclasses must implement this method"):
        agent.process(state)

def test_base_agent_state_type():
    # Given: A mock agent and full state
    agent = MockAgent("TestAgent")
    state = State(url="https://example.com", ticket_content="content", refined_ticket={"key": "value"}, result={}, generated_code="code", generated_tests="tests", existing_tests_passed=1, existing_coverage_all_files=50.0, relevant_code_files=[{"file_path": "a.ts", "content": "a"}], relevant_test_files=[{"file_path": "a.test.ts", "content": "test"}])

    # When: Processing the state
    result = agent(state)

    # Then: Result is dict with all State keys and correct types
    assert isinstance(result, dict)
    # Assert all State keys are present
    expected_keys = ['url', 'ticket_content', 'refined_ticket', 'result', 'generated_code', 'generated_tests', 'existing_tests_passed', 'existing_coverage_all_files', 'relevant_code_files', 'relevant_test_files']
    for key in expected_keys:
        assert key in result
    # Assert types
    assert isinstance(result['url'], str)
    assert isinstance(result['ticket_content'], str)
    assert isinstance(result['refined_ticket'], dict)
    assert isinstance(result['result'], dict)
    assert isinstance(result['generated_code'], str)
    assert isinstance(result['generated_tests'], str)
    assert isinstance(result['existing_tests_passed'], int)
    assert isinstance(result['existing_coverage_all_files'], float)
    assert isinstance(result['relevant_code_files'], list)
    assert isinstance(result['relevant_test_files'], list)

def test_base_agent_circuit_breaker_protection():
    # Given: A failing agent that raises exception and circuit breaker
    from unittest.mock import patch
    from src.circuit_breaker import CircuitBreaker

    class FailingAgent(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name)

        def process(self, state):
            raise ValueError("Simulated failure")

    agent = FailingAgent("FailingAgent")
    state = State(url="", ticket_content="", refined_ticket={}, result={}, generated_code="", generated_tests="", existing_tests_passed=0, existing_coverage_all_files=0.0, relevant_code_files=[], relevant_test_files=[])

    # When: Calling the agent multiple times to trigger circuit breaker
    # Then: Circuit breaker should handle failures appropriately
    with patch.object(agent.circuit_breaker, '_record_success') as mock_success, \
         patch.object(agent.circuit_breaker, '_record_failure') as mock_failure:

        # First failure
        with pytest.raises(ValueError):
            agent(state)
        mock_failure.assert_called_once()

        # Reset for next call
        mock_failure.reset_mock()

        # Second failure
        with pytest.raises(ValueError):
            agent(state)
        mock_failure.assert_called_once()
