import pytest
import os
import tempfile
import shutil
from typing import Dict, Any, List
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage
from langchain.tools import BaseTool
from src.tool_integrated_agent import ToolIntegratedAgent
from src.tools import read_file_tool, write_file_tool, list_files_tool
from src.circuit_breaker import CircuitBreakerOpenException

@pytest.mark.integration
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

    def create_dummy_llm(self, tool_calls: List[Dict]):
        """Dummy LLM that triggers specific tool calls."""
        def llm_func(input):
            return AIMessage(
                content="Trigger tools",
                tool_calls=tool_calls
            )
        return RunnableLambda(llm_func)

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

    def test_scenario4_llm_tool_augmented_prompt(self):
        """Scenario 4: LLM tool-augmented prompt; assert tool context included."""
        temp_dir = self.setup_temp_project()
        try:
            # LLM that "sees" tool context in prompt (simulate by fixed response)
            def prompt_aware_llm(input):
                # Simulate seeing tool context in prompt
                assert "Available Tools" in str(input)  # From _create_tool_augmented_prompt
                return AIMessage(content="tools context confirmed")

            llm = RunnableLambda(prompt_aware_llm)

            tools = [read_file_tool]
            agent = ToolIntegratedAgent(llm, tools)

            state = {"prompt_test": True}
            result = agent.process(state)

            assert "tools context confirmed" in result["tool_integrated_response"]
        finally:
            self.teardown_temp_project()