import pytest
import os
from typing import Dict, Any, List
from langchain_core.runnables import RunnableLambda
from langchain.tools import Tool
from langchain_core.messages import AIMessage
from src.agent_composer import AgentComposer, WorkflowConfig
from src.base_agent import BaseAgent
from src.tools import read_file_tool
from src.circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException
from src.state import State

@pytest.mark.integration
class TestAgentComposerIntegration:

    def test_scenario1_register_agents_tools_sequential_execution(self):
        """Scenario 1: Register 2 BaseAgent subclasses (dummy), 1 tool; sequential execution."""
        composer = AgentComposer()

        class DummyAgent1(BaseAgent):
            def process(self, state: State) -> State:
                state['history'] = state.get('history', []) + ['agent1_executed']
                return state

        class DummyAgent2(BaseAgent):
            def process(self, state: State) -> State:
                state['history'] = state.get('history', []) + ['agent2_executed']
                return state

        agent1 = DummyAgent1("dummy1")
        agent2 = DummyAgent2("dummy2")

        composer.register_agent("agent1", agent1)
        composer.register_agent("agent2", agent2)
        composer.register_tool("read_file", read_file_tool)

        config = WorkflowConfig(agent_names=["agent1", "agent2"], tool_names=["read_file"])

        workflow = composer.create_workflow("seq_test", config)

        initial_state: State = {"history": []}
        result = workflow.invoke(initial_state)

        assert len(result['history']) == 2
        assert result['history'] == ['agent1_executed', 'agent2_executed']

    @pytest.mark.parametrize("num_tools", [1, 2])
    def test_scenario2_parametrize_bind_tools(self, num_tools):
        """Scenario 2: Parametrize agents/tools bind_tools support."""
        composer = AgentComposer()

        class BindableAgent:
            def __init__(self):
                self.bound_tools = []

            def bind_tools(self, tools):
                self.bound_tools = tools
                return self

            def invoke(self, state, config=None):
                state['tool_context_bound'] = len(self.bound_tools) > 0
                state['num_tools_bound'] = len(self.bound_tools)
                return state

        bindable_agent = BindableAgent()
        composer.register_agent("bindable", bindable_agent)

        tools = [read_file_tool]
        for i in range(1, num_tools):
            tools.append(Tool(
                name=f"dummy_tool_{i}",
                description="dummy",
                func=lambda x: "dummy_result"
            ))

        for tool in tools:
            composer.register_tool(tool.name, tool)

        config = WorkflowConfig(agent_names=["bindable"], tool_names=[t.name for t in tools])

        workflow = composer.create_workflow("bind_test", config)

        initial_state = {}
        result = workflow.invoke(initial_state)

        assert result['tool_context_bound'] is True
        assert result['num_tools_bound'] == num_tools

    def test_scenario3_error_circuit_breaker(self):
        """Scenario 3: Error mid-workflow, circuit breaker trips."""
        composer = AgentComposer()

        class GoodAgent(BaseAgent):
            def process(self, state: State) -> State:
                state['history'] = state.get('history', []) + ['good_agent']
                return state

        class BadAgent(BaseAgent):
            def process(self, state: State) -> State:
                raise ValueError("simulated agent failure")

        good = GoodAgent("good")
        bad = BadAgent("bad")

        composer.register_agent("good", good)
        composer.register_agent("bad", bad)

        config = WorkflowConfig(agent_names=["good", "bad"], tool_names=[])
        workflow = composer.create_workflow("cb_test", config)

        state: State = {"history": []}

        # First 3 invocations fail with ValueError (threshold=3 for default)
        for _ in range(3):
            with pytest.raises(ValueError, match="simulated agent failure"):
                workflow.invoke(state)

        # 4th should trip circuit breaker
        with pytest.raises(CircuitBreakerOpenException):
            workflow.invoke(state)

        # Verify circuit breaker state for bad agent
        cb = get_circuit_breaker("bad")
        assert cb.failure_count >= 3
        assert cb.state.name == "OPEN"

    def test_scenario4_multi_agent_parallel(self):
        """Scenario 4: Multi-agent parallel using custom LCEL."""
        from langchain_core.runnables import RunnableParallel, RunnableLambda

        def agent_a(state):
            state['parallel_results'] = state.get('parallel_results', {})
            state['parallel_results']['A'] = 'result_A'
            return state

        def agent_b(state):
            state['parallel_results']['B'] = 'result_B'
            return state

        def combine_parallel(state):
            assert len(state['parallel_results']) == 2
            state['history'].append('parallel_complete')
            return state

        agent_a_r = RunnableLambda(agent_a)
        agent_b_r = RunnableLambda(agent_b)

        parallel_branch = RunnableParallel(agent_a=agent_a_r, agent_b=agent_b_r)
        parallel_workflow = parallel_branch | RunnableLambda(combine_parallel)

        initial_state = {'history': [], 'parallel_results': {}}
        result = parallel_workflow.invoke(initial_state)

        assert 'parallel_results' in result
        assert set(result['parallel_results'].keys()) == {'A', 'B'}
        assert len(result['history']) == 1
        assert result['history'][0] == 'parallel_complete'

    def test_scenario5_workflow_persistence_resume(self):
        """Scenario 5: Workflow persistence simulation with in-memory stub, resume mid-state."""
        composer = AgentComposer()

        class Agent1(BaseAgent):
            def process(self, state: State) -> State:
                state['history'].append('agent1')
                return state

        class Agent2(BaseAgent):
            def process(self, state: State) -> State:
                state['history'].append('agent2')
                return state

        agent1 = Agent1("agent1")
        agent2 = Agent2("agent2")

        composer.register_agent("agent1", agent1)
        composer.register_agent("agent2", agent2)

        config = WorkflowConfig(agent_names=["agent1", "agent2"], tool_names=[])
        workflow = composer.create_workflow("persist_test", config)

        # Simulate partial execution (only agent1)
        mid_state: State = {"history": []}
        mid_state = agent1.invoke(mid_state)  # manual partial

        # "Persist" mid_state (in-memory stub)
        persisted_state = mid_state.copy()

        # Resume with remaining workflow (agent2 only)
        resume_workflow = agent2  # stub as remaining chain
        final_state = resume_workflow.invoke(persisted_state)

        # Full workflow for comparison
        full_state = workflow.invoke({"history": []})

        assert len(final_state['history']) == 2
        assert final_state['history'] == ['agent1', 'agent2']
        assert final_state == full_state