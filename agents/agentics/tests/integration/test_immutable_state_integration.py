import pytest
import dataclasses

from src.state import CodeGenerationState
from src.base_agent import BaseAgent



@pytest.mark.integration
def test_state_transformation_chain(dummy_state):
    """State transformation chain: verifies with_* chain creates new immutable states."""
    base_state = dummy_state
    s1 = base_state.with_code('dummy_code')
    s2 = s1.with_tests('dummy_tests')

    assert id(s1) != id(base_state)
    assert id(s2) != id(s1)
    assert s2.generated_code == 'dummy_code'
    assert s2.generated_tests == 'dummy_tests'
    assert base_state.generated_code is None  # frozen/unchanged

    with pytest.raises(dataclasses.FrozenInstanceError):
        base_state.generated_code = 'mutated'  # test setattr raises


@pytest.mark.integration
def test_state_agent_integration(dummy_state, real_ollama_config):
    """State-agent integration: minimal BaseAgent subclass transforms state immutably."""
    class DummyAgent(BaseAgent):
        def __init__(self, config):
            super().__init__(name="DummyAgent")
            self.config = config  # minimally use config

        def process(self, state):
            return state.with_code('agent_updated')

    agent = DummyAgent(config=real_ollama_config)
    result = agent.process(dummy_state)

    assert isinstance(result, CodeGenerationState)
    assert result.generated_code == 'agent_updated'
    assert id(result) != id(dummy_state)