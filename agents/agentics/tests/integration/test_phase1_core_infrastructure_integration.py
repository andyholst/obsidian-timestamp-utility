import pytest
import os
import tempfile
import shutil
from typing import Dict, Any, List
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage
from src.agent_composer import AgentComposer, WorkflowConfig
from src.state import CodeGenerationState
from src.tool_integrated_agent import ToolIntegratedAgent
from src.base_agent import BaseAgent
from src.tools import read_file_tool, write_file_tool
from src.config import AgenticsConfig, init_config
from src.models import CodeSpec, TestSpec

@pytest.mark.integration
class TestPhase1CoreInfrastructureIntegration:

    def setup_temp_project_and_state(self):
        """Setup temp dir and initial state."""
        temp_dir = tempfile.mkdtemp(prefix="phase1_test_")
        os.environ["PROJECT_ROOT"] = temp_dir

        # Initial CodeGenerationState
        state = CodeGenerationState(
            issue_url="test/issue",
            ticket_content="integrated test",
            title="Phase1 Test",
            description="Full infrastructure test",
            requirements=["integrate all"],
            acceptance_criteria=["success"],
            code_spec=CodeSpec(language="ts"),
            test_spec=TestSpec(test_framework="jest")
        )
        return temp_dir, state

    def test_scenario1_full_phase1_flow(self):
        """Scenario 1: Composer + State + ToolIntegratedAgent + tools; end-state has results."""
        temp_dir, initial_state = self.setup_temp_project_and_state()
        try:
            # Dummy LLM for ToolIntegratedAgent that "generates" code/tests
            def gen_llm(input):
                return AIMessage(content="Generated: code and tests via tools")

            dummy_llm = RunnableLambda(gen_llm)
            tools = [read_file_tool, write_file_tool]
            tool_agent = ToolIntegratedAgent(dummy_llm, tools, name="tool_gen_agent")

            # Dummy state updater agent
            class StateUpdaterAgent(BaseAgent):
                def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
                    # Simulate adding results
                    state['generated_code'] = "phase1_code"
                    state['generated_tests'] = "phase1_tests"
                    state['tool_results'] = "files modified"
                    return state

            updater_agent = StateUpdaterAgent("updater")

            composer = AgentComposer()
            composer.register_agent("tool_agent", tool_agent)
            composer.register_agent("updater", updater_agent)
            composer.register_tool("read_file", read_file_tool)
            composer.register_tool("write_file", write_file_tool)

            config = WorkflowConfig(agent_names=["tool_agent", "updater"], tool_names=["read_file", "write_file"])
            workflow = composer.create_workflow("phase1_full", config)

            # Invoke on state (convert to dict for Runnable)
            state_dict = {k: str(v) if hasattr(v, '__dict__') else v for k, v in initial_state.__dict__.items()}
            result = workflow.invoke(state_dict)

            # Assert end-state has expected results
            assert 'generated_code' in result
            assert 'generated_tests' in result
            assert 'tool_results' in result
            assert 'tool_integrated_response' in result

            # Verify tool modified files
            output_file = os.path.join(temp_dir, "phase1_output.txt")
            assert os.path.exists(output_file)  # Assume tool writes it
        finally:
            shutil.rmtree(temp_dir)
            if "PROJECT_ROOT" in os.environ:
                del os.environ["PROJECT_ROOT"]

    @pytest.mark.parametrize("reasoning_model, code_model", [
        ("qwen2.5:0.5b", "qwen2.5-coder:1.5b"),
        ("llama3.1:8b", "deepseek-coder:6.7b")
    ])
    def test_scenario2_config_driven_llm_variation(self, reasoning_model, code_model):
        """Scenario 2: Config-driven AgenticsConfig; vary LLM models."""
        # Set env for config
        os.environ["OLLAMA_REASONING_MODEL"] = reasoning_model
        os.environ["OLLAMA_CODE_MODEL"] = code_model

        config = AgenticsConfig()
        init_config(config)

        assert config.ollama_reasoning_model == reasoning_model
        assert config.ollama_code_model == code_model

        # Verify config propagates (e.g., llm configs)
        reasoning_cfg = config.get_reasoning_llm_config()
        code_cfg = config.get_code_llm_config()
        assert reasoning_cfg.model == reasoning_model
        assert code_cfg.model == code_model

        # Dummy agent using config (simulate)
        class ConfigAwareAgent(BaseAgent):
            def process(self, state):
                state['config_model'] = config.ollama_code_model
                return state

        agent = ConfigAwareAgent("config_agent")
        result = agent.process({})
        assert result['config_model'] == code_model

    def test_scenario3_temp_project_tools_integration(self):
        """Scenario 3: Temp project dir; tools modify files; state reflects changes."""
        temp_dir, _ = self.setup_temp_project_and_state()
        try:
            # Tool agent that writes code/tests to files
            def write_code_llm(input):
                return AIMessage(
                    tool_calls=[{
                        "name": "write_file_tool",
                        "args": {"file_path": "generated_code.ts", "content": "// Phase1 code"}
                    }, {
                        "name": "write_file_tool",
                        "args": {"file_path": "generated_tests.test.ts", "content": "describe('phase1', () => {})"}
                    }]
                )

            llm = RunnableLambda(write_code_llm)
            tools = [write_file_tool]
            agent = ToolIntegratedAgent(llm, tools)

            state = {"project": temp_dir}
            result = agent.process(state)

            # Assert files created
            code_file = os.path.join(temp_dir, "generated_code.ts")
            test_file = os.path.join(temp_dir, "generated_tests.test.ts")
            assert os.path.exists(code_file)
            assert os.path.exists(test_file)

            with open(code_file) as f:
                assert "// Phase1 code" in f.read()
            with open(test_file) as f:
                assert "describe('phase1'" in f.read()

            assert "tool_integrated_response" in result
        finally:
            shutil.rmtree(temp_dir)
            if "PROJECT_ROOT" in os.environ:
                del os.environ["PROJECT_ROOT"]

    def test_scenario4_cross_component_data_flow(self):
        """Scenario 4: State → Agent → Composer → Tools; data flow integrity."""
        temp_dir, initial_state = self.setup_temp_project_and_state()
        try:
            # Agent1: processes state
            class PrepAgent(BaseAgent):
                def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
                    state['prepped'] = True
                    return state

            prep_agent = PrepAgent("prep")

            # Composer with tool agent
            def tool_llm(input):
                assert 'prepped' in input  # Data flow check
                return AIMessage(content="cross flow success")

            tool_llm_r = RunnableLambda(tool_llm)
            tools = [read_file_tool]
            tool_agent = ToolIntegratedAgent(tool_llm_r, tools)

            composer = AgentComposer()
            composer.register_agent("tool_agent", tool_agent)
            composer.register_tool("read_file", read_file_tool)

            config = WorkflowConfig(["tool_agent"], ["read_file"])
            workflow = composer.create_workflow("cross", config)

            # Flow: state -> prep_agent -> composer/workflow
            state_dict = {k: str(v) for k, v in initial_state.__dict__.items()}
            prepped = prep_agent.invoke(state_dict)
            final = workflow.invoke(prepped)

            # Assert data flow integrity
            assert final['prepped'] is True
            assert "cross flow success" in final.get('tool_integrated_response', '')
            assert isinstance(final, dict)
        finally:
            shutil.rmtree(temp_dir)
            if "PROJECT_ROOT" in os.environ:
                del os.environ["PROJECT_ROOT"]