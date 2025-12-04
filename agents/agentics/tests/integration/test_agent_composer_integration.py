import pytest
from dataclasses import asdict
from typing import List
from langchain_ollama import OllamaLLM

from src.agent_composer import AgentComposer, WorkflowConfig
from src.base_agent import BaseAgent
from src.tool_integrated_agent import ToolIntegratedAgent
from src.tools import read_file_tool, list_files_tool, write_file_tool
from src.circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException
from src.state import State


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["base+base", "base+tool_agent"])
async def test_sequential_multi_agent_workflow(
    case: str, real_ollama_config, temp_project_dir, dummy_state
):
    composer = AgentComposer()

    initial_state: State = asdict(dummy_state)

    class TestBaseAgent(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name)

        def process(self, state: State) -> State:
            state.setdefault("history", []).append(self.name)
            return state

    class TestToolAgent(ToolIntegratedAgent):
        def __init__(self, llm, name: str):
            super().__init__(llm, [], name)

        def bind_tools(self, tools):
            self.tools = tools
            return self

        def process(self, state: State) -> State:
            state.setdefault("history", []).append(self.name)
            return super().process(state)

    if case == "base+base":
        agent1 = TestBaseAgent("agent1")
        agent2 = TestBaseAgent("agent2")
        composer.register_agent("agent1", agent1)
        composer.register_agent("agent2", agent2)
        config = WorkflowConfig(agent_names=["agent1", "agent2"], tool_names=[])
        expected_history = ["agent1", "agent2"]
    else:
        llm = OllamaLLM(
            model=real_ollama_config.ollama_code_model,
            base_url=real_ollama_config.ollama_host,
            temperature=0.1,
        )
        base_agent = TestBaseAgent("base")
        tool_agent = TestToolAgent(llm, "tool_agent")
        composer.register_agent("base", base_agent)
        composer.register_agent("tool_agent", tool_agent)
        composer.register_tool("read_file_tool", read_file_tool)
        config = WorkflowConfig(agent_names=["base", "tool_agent"], tool_names=["read_file_tool"])
        expected_history = ["base", "tool_agent"]

    workflow = composer.create_workflow("sequential_test", config)
    result = await workflow.ainvoke(initial_state)

    assert isinstance(result, dict)
    assert "history" in result
    assert len(result["history"]) == 2
    assert result["history"] == expected_history


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("num_tools", [1, 2, 3])
async def test_tool_binding_in_workflow(
    num_tools: int, real_ollama_config, temp_project_dir, dummy_state
):
    composer = AgentComposer()

    initial_state: State = asdict(dummy_state)

    class BindableTestAgent(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name)
            self._num_tools_bound = 0

        def bind_tools(self, tools):
            self._num_tools_bound = len(tools)
            self.tools = tools
            return self

        def process(self, state: State) -> State:
            state["num_tools_bound"] = self._num_tools_bound
            return state

    agent = BindableTestAgent("bindable")
    composer.register_agent("bindable", agent)

    all_tools = [read_file_tool, list_files_tool, write_file_tool]
    tools_to_use = all_tools[:num_tools]
    for tool in tools_to_use:
        composer.register_tool(tool.name, tool)

    config = WorkflowConfig(
        agent_names=["bindable"], tool_names=[tool.name for tool in tools_to_use]
    )
    workflow = composer.create_workflow("tool_binding_test", config)
    assert hasattr(agent, 'tools')
    assert len(agent.tools) == num_tools
    result = await workflow.ainvoke(initial_state)

    assert result.get("num_tools_bound") == num_tools


@pytest.mark.integration
@pytest.mark.asyncio
async def test_workflow_error_propagation_circuit_breaker(
    real_ollama_config, temp_project_dir, dummy_state
):
    composer = AgentComposer()

    initial_state: State = asdict(dummy_state)

    class GoodAgent(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name)

        def process(self, state: State) -> State:
            state.setdefault("history", []).append("good")
            return state

    class BadAgent(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name)

        def process(self, state: State) -> State:
            raise Exception("mid-agent failure")

    good = GoodAgent("good")
    bad = BadAgent("bad")
    composer.register_agent("good", good)
    composer.register_agent("bad", bad)

    config = WorkflowConfig(agent_names=["good", "bad"], tool_names=[])
    workflow = composer.create_workflow("error_propagation_test", config)

    # First 3 invocations fail with Exception
    for _ in range(3):
        with pytest.raises(Exception, match="mid-agent failure"):
            await workflow.ainvoke(initial_state)

    # 4th should trip circuit breaker
    with pytest.raises(CircuitBreakerOpenException):
        await workflow.ainvoke(initial_state)

    cb = get_circuit_breaker("bad")
    assert cb.failure_count >= 3
    assert cb.state.name == "OPEN"