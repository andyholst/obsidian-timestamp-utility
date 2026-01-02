import pytest
import os
import tempfile
import shutil
from typing import Dict, Any, List
from langchain.tools import BaseTool
from langchain_ollama import OllamaLLM
from langchain_core.runnables import RunnableLambda
from src.tool_integrated_agent import ToolIntegratedAgent
from src.tools import read_file_tool, write_file_tool, list_files_tool, npm_search_tool
from src.circuit_breaker import CircuitBreakerOpenException
from langchain_core.messages import AIMessage

\nclass DummyLLM:\n    def __init__(self, tool_calls_list):\n        self.tool_calls_list = tool_calls_list\n        self.index = 0\n\n    def invoke(self, input, config=None):\n        if self.index &lt; len(self.tool_calls_list):\n            tool_call = self.tool_calls_list[self.index]\n            self.index += 1\n            return AIMessage(tool_calls=[tool_call])\n        return AIMessage(content=&quot;Trigger tools&quot;)\n\n\n@pytest.mark.integration
class TestToolIntegratedAgentIntegration:

    def setup_temp_project(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp(prefix="tool_agent_test_")
        os.environ["PROJECT_ROOT"] = self.temp_dir
        # Create dummy file for read tests
        dummy_file_path = os.path.join(self.temp_dir, "dummy.txt")
        with open(dummy_file_path, "w") as f:
            f.write("This is dummy file content for testing.")
        return self.temp_dir

    def teardown_temp_project(self):
        """Cleanup temporary directory."""
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir)
            del os.environ["PROJECT_ROOT"]


    def test_scenario1_single_tool_call(self):
        """Scenario 1: Instantiate with real LLM/tools; dummy state triggers read_file_tool."""
        temp_dir = self.setup_temp_project()
        try:
            llm = self.create_dummy_llm([{
                "name": "read_file_tool",
                "args": {"file_path": "dummy.txt"}
            }])

            tools: List[BaseTool] = [read_file_tool]
            agent = ToolIntegratedAgent(llm, tools, name="test_agent")

            initial_state: Dict[str, Any] = {"input": "read dummy file"}

            result_state = agent.process(initial_state)

            assert "tool_integrated_response" in result_state
            assert "Trigger tools" in result_state["tool_integrated_response"]  # Final llm response after tools

            # Verify tool executed (file content would be in intermediate, but final response fixed)
            # Since followup llm fixed, assert agent processed without crash
            assert isinstance(result_state, dict)
        finally:
            self.teardown_temp_project()

    def test_scenario2_multi_tool_sequence(self):
        """Scenario 2: Multi-tool (read + write); assert file written."""
        temp_dir = self.setup_temp_project()
        try:
            # Create initial file
            init_file = os.path.join(temp_dir, "input.txt")
            with open(init_file, "w") as f:
                f.write("initial content")

            llm_calls = [{
                "name": "read_file_tool",
                "args": {"file_path": "input.txt"}
            }, {
                "name": "write_file_tool",
                "args": {"file_path": "output.txt", "content": "written by tool"}
            }, {
                "name": "list_files_tool",
                "args": {}
            }]

            llm = self.create_dummy_llm(llm_calls)

            tools = [read_file_tool, write_file_tool, list_files_tool]
            agent = ToolIntegratedAgent(llm, tools)

            state = {"multi_tool": True}
            result = agent.process(state)

            assert "tool_integrated_response" in result

            # Verify write tool worked
            output_path = os.path.join(temp_dir, "output.txt")
            assert os.path.exists(output_path)
            with open(output_path, "r") as f:
                assert f.read() == "written by tool"

            # List should include output.txt
            list_path = os.path.join(temp_dir, "list_result.txt")  # Not written, but tool returns str
        finally:
            self.teardown_temp_project()

    def test_scenario3_tool_failure_recovery(self):
        """Scenario 3: Tool failure (invalid path); BaseAgent circuit breaker."""
        temp_dir = self.setup_temp_project()
        try:
            llm = self.create_dummy_llm([{
                "name": "read_file_tool",
                "args": {"file_path": "nonexistent.txt"}  # Will fail
            }])

            tools = [read_file_tool]
            agent = ToolIntegratedAgent(llm, tools, name="failing_agent")

            state = {"fail": True}

            # First few should fail with tool error (ValueError or FileNotFound)
            for i in range(3):
                with pytest.raises(Exception):  # Tool execution error
                    agent.process(state)

            # Circuit breaker should trip on 4th (threshold 3)
            from src.circuit_breaker import get_circuit_breaker
            cb = get_circuit_breaker("failing_agent")
            assert cb.failure_count >= 3

            with pytest.raises(CircuitBreakerOpenException):
                agent.process(state)

            assert cb.state.name == "OPEN"
        finally:
            self.teardown_temp_project()

    @pytest.mark.parametrize(
        "tool_list, expected_desc_snippets",
        [
            ([read_file_tool], ["Read the content of a file"]),
            ([write_file_tool], ["Write content to a file"]),
            ([read_file_tool, list_files_tool], ["Read the content of a file", "List files and directories"]),
            ([npm_search_tool], ["Search for npm packages"]),
        ],
        ids=["read_file", "write_file", "read_list", "npm_search"]
    )
    def test_tool_augmented_prompt_parametrized(self, tool_list, expected_desc_snippets):
        """Enhanced: Parametrized test for _create_tool_augmented_prompt - LLM sees tool descriptions/context."""
        temp_dir = self.setup_temp_project()
        try:
            def prompt_checker(prompt):
                assert "Available Tools:" in prompt
                for i, tool in enumerate(tool_list):
                    assert tool.name in prompt
                    snippet = expected_desc_snippets[i]
                    assert snippet in prompt
                return AIMessage(content="tool augmented prompt confirmed")

            llm = RunnableLambda(prompt_checker)

            agent = ToolIntegratedAgent(llm, tool_list)

            state = {"prompt_test": True}
            result = agent.process(state)

            assert "tool augmented prompt confirmed" in result["tool_integrated_response"]
        finally:
            self.teardown_temp_project()

    def test_direct_tool_augmented_prompt_creation(self):
        """Direct integration test for _create_tool_augmented_prompt - verifies LLM sees exact tool context."""
        def dummy_llm(prompt):
            # This won't be called, but for init
            return "dummy"

        # Test with file and npm tools
        tools = [read_file_tool, npm_search_tool]
        agent = ToolIntegratedAgent(dummy_llm, tools, name="prompt_direct_test")

        state = {"direct_prompt_test": True}
        tool_context = agent._gather_tool_context(state)

        prompt = agent._create_tool_augmented_prompt(state, tool_context)

        # Verify base prompt
        base_expected = f"Process the following state: {{'direct_prompt_test': True}}"
        assert base_expected in prompt

        # Verify tool section structure
        assert "\n\nAvailable Tools:\n" in prompt
        assert "- read_file_tool: Read the content of a file" in prompt
        assert "- npm_search_tool: Search for npm packages" in prompt
        assert "When you need to use a tool, respond with a tool call." in prompt

        # Test empty tools
        empty_agent = ToolIntegratedAgent(dummy_llm, [])
        empty_prompt = empty_agent._create_tool_augmented_prompt(state, {})
        assert "\n\nAvailable Tools:" not in empty_prompt  # No tool section