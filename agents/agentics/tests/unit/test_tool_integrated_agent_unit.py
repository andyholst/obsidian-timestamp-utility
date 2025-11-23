import pytest
import os
from unittest.mock import MagicMock, patch, mock_open
from langchain_core.tools import BaseTool

# Mock environment variables to avoid initialization issues
os.environ.setdefault('PROJECT_ROOT', '/tmp')
os.environ.setdefault('GITHUB_TOKEN', 'dummy_token')

# Mock the problematic imports at the module level
with patch.dict('sys.modules', {
    'src.agentics': MagicMock(),
    'src.code_extractor_agent': MagicMock(),
    'src.circuit_breaker': MagicMock(),
    'src.monitoring': MagicMock(),
}):
    from src.tool_integrated_agent import ToolIntegratedAgent
    from src.state import State


@pytest.fixture
def mock_llm():
    """Mock LLM that returns configurable responses."""
    llm = MagicMock()
    return llm


@pytest.fixture
def mock_tools():
    """Create mock tools for testing."""
    tool1 = MagicMock(spec=BaseTool)
    tool1.name = "read_file"
    tool1.description = "Read file contents"

    tool2 = MagicMock(spec=BaseTool)
    tool2.name = "list_files"
    tool2.description = "List directory contents"

    return [tool1, tool2]


@pytest.fixture
def mock_response_no_tools():
    """Mock LLM response without tool calls."""
    response = MagicMock()
    response.tool_calls = None
    response.content = "Processed without tools"
    return response


@pytest.fixture
def mock_response_with_tools():
    """Mock LLM response with tool calls."""
    response = MagicMock()
    response.tool_calls = [
        {"name": "read_file", "args": {"file_path": "test.txt"}},
        {"name": "list_files", "args": {"directory": "."}}
    ]
    response.content = "Need to use tools"
    return response


@pytest.fixture
def mock_response_no_content():
    """Mock LLM response without content attribute."""
    response = MagicMock()
    response.tool_calls = None
    del response.content  # No content attribute
    return response


@pytest.fixture
def sample_state():
    """Sample state for testing."""
    return State(
        url="https://example.com",
        ticket_content="Test ticket",
        refined_ticket={},
        result={},
        generated_code="",
        generated_tests="",
        existing_tests_passed=0,
        existing_coverage_all_files=0.0,
        relevant_code_files=[],
        relevant_test_files=[]
    )


def test_tool_integrated_agent_init(mock_llm, mock_tools):
    """Test ToolIntegratedAgent initialization."""
    # When: Creating agent with LLM and tools
    agent = ToolIntegratedAgent(mock_llm, mock_tools)

    # Then: Agent is properly initialized
    assert agent.llm == mock_llm
    assert agent.tools == mock_tools
    assert agent.name == "ToolIntegratedAgent"
    assert hasattr(agent, 'tool_executor')


def test_gather_tool_context(mock_llm, mock_tools, sample_state):
    """Test gathering tool context from state."""
    agent = ToolIntegratedAgent(mock_llm, mock_tools)

    # When: Gathering tool context
    context = agent._gather_tool_context(sample_state)

    # Then: Context contains available tools and descriptions
    assert "available_tools" in context
    assert "tool_descriptions" in context
    assert context["available_tools"] == ["read_file", "list_files"]
    assert context["tool_descriptions"]["read_file"] == "Read file contents"
    assert context["tool_descriptions"]["list_files"] == "List directory contents"


def test_create_tool_augmented_prompt_with_tools(mock_llm, mock_tools, sample_state):
    """Test creating tool-augmented prompt when tools are available."""
    agent = ToolIntegratedAgent(mock_llm, mock_tools)

    tool_context = agent._gather_tool_context(sample_state)

    # When: Creating tool-augmented prompt
    prompt = agent._create_tool_augmented_prompt(sample_state, tool_context)

    # Then: Prompt includes base state and tool information
    assert str(sample_state) in prompt
    assert "Available Tools:" in prompt
    assert "read_file: Read file contents" in prompt
    assert "list_files: List directory contents" in prompt
    assert "When you need to use a tool, respond with a tool call." in prompt


def test_create_tool_augmented_prompt_no_tools(mock_llm, sample_state):
    """Test creating prompt when no tools are available."""
    agent = ToolIntegratedAgent(mock_llm, [])

    tool_context = agent._gather_tool_context(sample_state)

    # When: Creating prompt without tools
    prompt = agent._create_tool_augmented_prompt(sample_state, tool_context)

    # Then: Prompt is just the base state
    assert prompt == f"Process the following state: {sample_state}"


def test_create_followup_prompt(mock_llm, mock_tools, mock_response_with_tools):
    """Test creating followup prompt with tool results."""
    agent = ToolIntegratedAgent(mock_llm, mock_tools)

    tool_results = {"read_file": "file content", "list_files": "file1.txt, file2.txt"}

    # When: Creating followup prompt
    prompt = agent._create_followup_prompt(mock_response_with_tools, tool_results)

    # Then: Prompt includes previous response and tool results
    assert "Previous response:" in prompt
    assert "Tool results:" in prompt
    assert "read_file: file content" in prompt
    assert "list_files: file1.txt, file2.txt" in prompt
    assert "Continue processing based on the tool results." in prompt


def test_needs_tool_execution_with_tools(mock_response_with_tools):
    """Test detecting when tools need execution."""
    agent = ToolIntegratedAgent(MagicMock(), [])

    # When: Checking response with tool calls
    needs_execution = agent._needs_tool_execution(mock_response_with_tools)

    # Then: Should return truthy value (the tool_calls list)
    assert needs_execution  # tool_calls list is truthy


def test_needs_tool_execution_no_tools(mock_response_no_tools):
    """Test detecting when tools don't need execution."""
    agent = ToolIntegratedAgent(MagicMock(), [])

    # When: Checking response without tool calls
    needs_execution = agent._needs_tool_execution(mock_response_no_tools)

    # Then: Should return falsy value (None)
    assert not needs_execution  # None is falsy


def test_needs_tool_execution_no_tool_calls_attribute():
    """Test detecting when response has no tool_calls attribute."""
    agent = ToolIntegratedAgent(MagicMock(), [])
    response = MagicMock()
    del response.tool_calls  # No tool_calls attribute

    # When: Checking response without tool_calls attribute
    needs_execution = agent._needs_tool_execution(response)

    # Then: Should return False
    assert needs_execution is False


def test_update_state_with_response(mock_llm, mock_tools, sample_state, mock_response_no_tools):
    """Test updating state with response content."""
    agent = ToolIntegratedAgent(mock_llm, mock_tools)

    # When: Updating state with response
    updated_state = agent._update_state_with_response(sample_state, mock_response_no_tools)

    # Then: State has tool_integrated_response key
    assert "tool_integrated_response" in updated_state
    assert updated_state["tool_integrated_response"] == "Processed without tools"


def test_update_state_with_response_no_content(mock_llm, mock_tools, sample_state, mock_response_no_content):
    """Test updating state when response has no content attribute."""
    agent = ToolIntegratedAgent(mock_llm, mock_tools)

    # When: Updating state with response without content
    updated_state = agent._update_state_with_response(sample_state, mock_response_no_content)

    # Then: State has tool_integrated_response as string representation
    assert "tool_integrated_response" in updated_state
    assert isinstance(updated_state["tool_integrated_response"], str)


@patch('src.tool_integrated_agent.ToolExecutor')
def test_process_with_tools_no_tool_calls(mock_tool_executor, mock_llm, mock_tools, sample_state, mock_response_no_tools):
    """Test processing state when no tool calls are needed."""
    agent = ToolIntegratedAgent(mock_llm, mock_tools)
    mock_llm.invoke.return_value = mock_response_no_tools

    # When: Processing state without tool calls
    result = agent.process_with_tools(sample_state)

    # Then: LLM invoked once, tool executor not used
    mock_llm.invoke.assert_called_once()
    mock_tool_executor.return_value.execute.assert_not_called()
    assert "tool_integrated_response" in result
    assert result["tool_integrated_response"] == "Processed without tools"


def test_process_with_tools_with_tool_calls(mock_llm, mock_tools, sample_state, mock_response_with_tools, mock_response_no_tools):
    """Test processing state with successful tool calls."""
    agent = ToolIntegratedAgent(mock_llm, mock_tools)

    # Mock the tool_executor
    agent.tool_executor = MagicMock()
    tool_results = {"read_file": "content", "list_files": "files"}
    agent.tool_executor.execute.return_value = tool_results

    # Setup LLM responses
    mock_llm.invoke.side_effect = [mock_response_with_tools, mock_response_no_tools]

    # When: Processing state with tool calls
    result = agent.process_with_tools(sample_state)

    # Then: LLM invoked twice, tool executor used
    assert mock_llm.invoke.call_count == 2
    agent.tool_executor.execute.assert_called_once_with(mock_response_with_tools)
    assert "tool_integrated_response" in result
    assert result["tool_integrated_response"] == "Processed without tools"


def test_process_with_tools_tool_execution_failure(mock_llm, mock_tools, sample_state, mock_response_with_tools, mock_response_no_tools):
    """Test processing state when tool execution fails."""
    agent = ToolIntegratedAgent(mock_llm, mock_tools)

    # Mock the tool_executor to return error results
    agent.tool_executor = MagicMock()
    tool_results = {"read_file": "Error: Tool execution failed", "list_files": "Error: Tool execution failed"}
    agent.tool_executor.execute.return_value = tool_results

    # Setup LLM responses
    mock_llm.invoke.side_effect = [mock_response_with_tools, mock_response_no_tools]

    # When: Processing should complete even with tool errors
    result = agent.process_with_tools(sample_state)

    # Then: LLM invoked twice (followup still called), tool executor used
    assert mock_llm.invoke.call_count == 2
    agent.tool_executor.execute.assert_called_once_with(mock_response_with_tools)
    assert "tool_integrated_response" in result


def test_process_with_tools_empty_tools_list(mock_llm, sample_state, mock_response_no_tools):
    """Test processing with empty tools list."""
    agent = ToolIntegratedAgent(mock_llm, [])
    mock_llm.invoke.return_value = mock_response_no_tools

    # When: Processing with no tools
    result = agent.process_with_tools(sample_state)

    # Then: Works normally, no tool execution attempted
    mock_llm.invoke.assert_called_once()
    assert "tool_integrated_response" in result


def test_process_with_tools_llm_failure(mock_llm, mock_tools, sample_state):
    """Test error handling when LLM fails."""
    agent = ToolIntegratedAgent(mock_llm, mock_tools)
    mock_llm.invoke.side_effect = Exception("LLM failure")

    # When/Then: Processing raises exception
    with pytest.raises(Exception, match="LLM failure"):
        agent.process_with_tools(sample_state)


def test_tool_integrated_agent_inheritance(mock_llm, mock_tools):
    """Test that ToolIntegratedAgent properly inherits from BaseAgent."""
    agent = ToolIntegratedAgent(mock_llm, mock_tools)

    # Then: Has BaseAgent attributes
    assert hasattr(agent, 'name')
    assert hasattr(agent, 'logger')
    assert hasattr(agent, 'circuit_breaker')