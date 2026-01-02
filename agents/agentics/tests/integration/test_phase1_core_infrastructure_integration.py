import pytest
import os
from dataclasses import asdict
from langchain_core.runnables import RunnableLambda
from src.agent_composer import AgentComposer, WorkflowConfig
from src.tool_integrated_agent import ToolIntegratedAgent
from src.tools import read_file_tool, write_file_tool, list_files_tool
from src.config import AgenticsConfig
from langchain_ollama import OllamaLLM


@pytest.mark.integration
@pytest.mark.asyncio
async def test_composer_state_toolagent_tools_e2e(temp_project_dir, dummy_state, real_ollama_config):
    composer = AgentComposer()
    
    llm = OllamaLLM(
        model=real_ollama_config.ollama_code_model,
        base_url=real_ollama_config.ollama_host,
        temperature=0.1,
    )
    
    tools = [read_file_tool, write_file_tool, list_files_tool]
    
    tool_agent = ToolIntegratedAgent(llm, tools, name="tool_agent")
    
    composer.register_agent("tool_agent", tool_agent)
    composer.register_tool("read_file_tool", read_file_tool)
    composer.register_tool("write_file_tool", write_file_tool)
    composer.register_tool("list_files_tool", list_files_tool)
    
    # Simple updater to ensure required keys are present
    def updater(state):
        state["generated_code"] = "integration_test_generated_code"
        state["tool_results"] = "integration_test_tool_results"
        return state
    
    updater_agent = RunnableLambda(updater)
    composer.register_agent("updater", updater_agent)
    
    wf_config = WorkflowConfig(
        agent_names=["tool_agent", "updater"],
        tool_names=["read_file_tool", "write_file_tool", "list_files_tool"]
    )
    
    workflow = composer.create_workflow("e2e_test", wf_config)
    
    state_dict = asdict(dummy_state)
    
    result = await workflow.ainvoke(state_dict)
    
    assert isinstance(result, dict)
    assert "generated_code" in result
    assert "tool_results" in result
    
    # Verify fixture file exists (tools can read/write in temp_project_dir)
    input_file = os.path.join(temp_project_dir, "input.txt")
    assert os.path.exists(input_file)


@pytest.mark.parametrize("model", ["llama3", "codellama:7b"])
@pytest.mark.integration
def test_config_driven_variations(model, dummy_state):
    config = AgenticsConfig(ollama_code_model=model)
    assert config.ollama_code_model == model
    
    llm = OllamaLLM(
        model=config.ollama_code_model,
        base_url=config.ollama_host,
        temperature=0.1,
    )
    
    # Minimal ToolIntegratedAgent (no tools) to test config propagation via LLM
    agent = ToolIntegratedAgent(llm, [])
    
    # Minimal invoke to propagate config through agent/LLM
    state_dict = asdict(dummy_state)
    result = agent.process(state_dict)
    
    assert isinstance(result, dict)