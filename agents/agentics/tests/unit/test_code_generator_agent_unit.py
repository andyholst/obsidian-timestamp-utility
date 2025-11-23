import pytest
import os
from unittest.mock import patch, MagicMock
from src.code_generator_agent import CodeGeneratorAgent
from src.state import State
from tests.fixtures.mock_llm_responses import create_code_generator_mock_responses

@pytest.fixture
def mock_code_generator_llm():
    """Provide mock LLM responses for CodeGeneratorAgent tests."""
    return create_code_generator_mock_responses()

@patch.dict(os.environ, {"PROJECT_ROOT": "/tmp/test"})
@patch('src.code_generator_agent.npm_list_tool', return_value='{"dependencies": {"uuid": "1.0.0"}}')
def test_code_generator_agent_process_with_requirements(mock_npm_list, mock_code_generator_llm):
    """Test CodeGeneratorAgent process with requirements using mock LLM."""
    agent = CodeGeneratorAgent(mock_code_generator_llm["code_generation"])
    state = State(
        result={
            "title": "Add UUID Generator",
            "description": "Add a command to generate UUIDs",
            "requirements": ["Generate UUID v7", "Insert at cursor"],
            "acceptance_criteria": ["UUID is valid", "Inserted correctly"]
        },
        relevant_code_files=[
            {"file_path": "src/main.ts", "content": "class TimestampPlugin extends obsidian.Plugin {}"}
        ],
        relevant_test_files=[
            {"file_path": "src/__tests__/main.test.ts", "content": "describe('TimestampPlugin', () => {});"}
        ],
        code_structure={"classes": ["TimestampPlugin"], "methods": []},
        test_structure={"describes": ["TimestampPlugin"]}
    )

    # When: Processing with mock LLM
    result = agent.process(state)

    # Then: Verify generated code and tests
    assert "generated_code" in result, "Generated code should be present"
    assert "generated_tests" in result, "Generated tests should be present"
    assert isinstance(result["generated_code"], str), "Generated code should be a string"
    assert isinstance(result["generated_tests"], str), "Generated tests should be a string"
    assert len(result["generated_code"]) > 0, "Generated code should not be empty"
    assert len(result["generated_tests"]) > 0, "Generated tests should not be empty"
    # Basic content checks
    assert "function" in result["generated_code"] or "class" in result["generated_code"], "Code should contain functions or classes"
    assert "test" in result["generated_tests"] or "describe" in result["generated_tests"], "Tests should contain test blocks"

@patch.dict(os.environ, {"PROJECT_ROOT": "/tmp/test"})
@patch('src.code_generator_agent.npm_list_tool', return_value='{"dependencies": {}}')
def test_code_generator_agent_process_vague_ticket(mock_npm_list, mock_code_generator_llm):
    """Test CodeGeneratorAgent skips generation for vague tickets using mock LLM."""
    agent = CodeGeneratorAgent(mock_code_generator_llm["vague"])
    state = State(
        result={
            "title": "Vague Feature",
            "description": "Some feature",
            "requirements": [],
            "acceptance_criteria": []
        },
        relevant_code_files=[
            {"file_path": "src/main.ts", "content": "class TimestampPlugin extends obsidian.Plugin {}"}
        ],
        relevant_test_files=[
            {"file_path": "src/__tests__/main.test.ts", "content": "describe('TimestampPlugin', () => {});"}
        ]
    )

    # When: Processing vague ticket
    result = agent.process(state)

    # Then: Generation skipped
    assert result["generated_code"] == "", "Generated code should be empty for vague tickets"
    assert result["generated_tests"] == "", "Generated tests should be empty for vague tickets"

@patch.dict(os.environ, {"PROJECT_ROOT": "/tmp/test"})
@patch('src.code_generator_agent.npm_list_tool', return_value='{"dependencies": {}}')
def test_code_generator_agent_process_empty_requirements(mock_npm_list, mock_code_generator_llm):
    """Test CodeGeneratorAgent with empty requirements but non-empty acceptance criteria."""
    agent = CodeGeneratorAgent(mock_code_generator_llm["vague"])
    state = State(
        result={
            "title": "Feature with AC only",
            "description": "Feature description",
            "requirements": [],
            "acceptance_criteria": ["Should work"]
        },
        relevant_code_files=[
            {"file_path": "src/main.ts", "content": "class TimestampPlugin extends obsidian.Plugin {}"}
        ],
        relevant_test_files=[
            {"file_path": "src/__tests__/main.test.ts", "content": "describe('TimestampPlugin', () => {});"}
        ]
    )

    # When: Processing
    result = agent.process(state)

    # Then: Skipped due to empty requirements
    assert result["generated_code"] == "", "Should skip if requirements empty"
    assert result["generated_tests"] == "", "Should skip if requirements empty"

@patch.dict(os.environ, {"PROJECT_ROOT": "/tmp/test"})
def test_code_generator_agent_initialization(mock_code_generator_llm):
    """Test CodeGeneratorAgent initialization."""
    agent = CodeGeneratorAgent(mock_code_generator_llm["code_generation"])
    assert agent.name == "CodeGenerator"
    assert agent.llm == mock_code_generator_llm["code_generation"]
    assert hasattr(agent, 'code_generation_chain')
    assert hasattr(agent, 'test_generation_chain')
    assert hasattr(agent, 'code_correction_chain')

@patch.dict(os.environ, {"PROJECT_ROOT": "/tmp/test"})
@patch('src.code_generator_agent.npm_list_tool', return_value='{"dependencies": {"uuid": "1.0.0"}}')
def test_code_generator_agent_process_with_feedback(mock_npm_list, mock_code_generator_llm):
    """Test CodeGeneratorAgent process with feedback from previous iteration."""
    agent = CodeGeneratorAgent(mock_code_generator_llm["feedback"])
    state = State(
        result={
            "title": "Add UUID Generator",
            "description": "Add a command to generate UUIDs",
            "requirements": ["Generate UUID v7"],
            "acceptance_criteria": ["UUID is valid"]
        },
        relevant_code_files=[
            {"file_path": "src/main.ts", "content": "class TimestampPlugin extends obsidian.Plugin {}"}
        ],
        relevant_test_files=[
            {"file_path": "src/__tests__/main.test.ts", "content": "describe('TimestampPlugin', () => {});"}
        ],
        feedback={"feedback": "Add error handling", "is_aligned": False, "needs_fix": True}
    )

    # When: Processing with feedback
    result = agent.process(state)

    # Then: Should still generate, incorporating feedback
    assert "generated_code" in result
    assert "generated_tests" in result
    assert len(result["generated_code"]) > 0
def test_code_generator_agent_generated_code_quality():
    """Test that generated code has basic TypeScript quality using real LLM."""
    agent = CodeGeneratorAgent(llm)
    state = State(
        result={
            "title": "Add Function",
            "description": "Add a simple function",
            "requirements": ["Add a function that returns hello"],
            "acceptance_criteria": ["Function returns 'hello'"]
        },
        relevant_code_files=[
            {"file_path": "src/main.ts", "content": "class TimestampPlugin extends obsidian.Plugin {}"}
        ],
        relevant_test_files=[
            {"file_path": "src/__tests__/main.test.ts", "content": "describe('TimestampPlugin', () => {});"}
        ]
    )

    result = agent.process(state)

    # Enhanced assertions for code quality
    code = result["generated_code"]
    assert "public" in code or "private" in code or "function" in code, "Code should have access modifiers or functions"
    assert "{" in code and "}" in code, "Code should have braces"
    assert ";" in code or code.strip().endswith("}"), "Code should have semicolons or proper closing"
    # Check for common TypeScript elements
    assert any(keyword in code for keyword in ["import", "export", "class", "interface", "function"]), "Code should contain TypeScript keywords"

def test_code_generator_agent_generated_tests_quality():
    """Test that generated tests have basic Jest quality using real LLM."""
    agent = CodeGeneratorAgent(llm)
    state = State(
        result={
            "title": "Add Test",
            "description": "Add a test for a function",
            "requirements": ["Test the function"],
            "acceptance_criteria": ["Test passes"]
        },
        relevant_code_files=[
            {"file_path": "src/main.ts", "content": "class TimestampPlugin extends obsidian.Plugin {}"}
        ],
        relevant_test_files=[
            {"file_path": "src/__tests__/main.test.ts", "content": "describe('TimestampPlugin', () => {});"}
        ]
    )

    result = agent.process(state)

    # Enhanced assertions for test quality
    tests = result["generated_tests"]
    assert "describe(" in tests, "Tests should have describe blocks"
    assert "test(" in tests or "it(" in tests, "Tests should have test/it blocks"
    assert "expect(" in tests or "assert" in tests, "Tests should have assertions"
    assert "TimestampPlugin" in tests, "Tests should reference the plugin"

def test_code_generator_agent_chain_error_handling():
    """Test chain error handling with invalid state using real LLM."""
    agent = CodeGeneratorAgent(llm)
    # Invalid state missing required keys
    state = State(
        result={
            "title": "Invalid",
            "description": "",
            "requirements": ["Invalid"],
            "acceptance_criteria": ["Invalid"]
        },
        # Missing relevant_code_files
    )


    # Should handle gracefully or raise appropriate error
    try:
        result = agent.process(state)
        # If it succeeds, check minimal output
        assert "generated_code" in result
        assert "generated_tests" in result
    except KeyError as e:
        assert "relevant_code_files" in str(e) or "result" in str(e), "Should raise KeyError for missing keys"

def test_code_generator_agent_langchain_chain_invocation():
    """Test direct chain invocation for LangChain validation using real LLM."""
    agent = CodeGeneratorAgent(llm)
    # Test code generation chain directly
    test_state = {
        "result": {
            "title": "Test Chain",
            "description": "Test direct chain call",
            "requirements": ["Generate code"],
            "acceptance_criteria": ["Code is valid"]
        },
        "relevant_code_files": [{"file_path": "src/main.ts", "content": "class Test {}"}],
        "relevant_test_files": [{"file_path": "src/__tests__/main.test.ts", "content": "describe('Test', () => {});"}],
        "code_structure": {},
        "test_structure": {},
        "feedback": {}
    }

    # Invoke chain directly
    generated_code = agent.code_generation_chain.invoke(test_state)
    assert isinstance(generated_code, str), "Chain should return string"
    assert len(generated_code) > 0, "Generated code should not be empty"
    assert "function" in generated_code or "class" in generated_code, "Should generate code-like content"

def test_code_generator_agent_test_chain_invocation():
    """Test test generation chain directly for LangChain validation using real LLM."""
    agent = CodeGeneratorAgent(llm)
    test_state = {
        "result": {
            "title": "Test Chain",
            "description": "Test test chain",
            "requirements": ["Generate tests"],
            "acceptance_criteria": ["Tests are valid"]
        },
        "generated_code": "function test() {}",
        "relevant_code_files": [{"file_path": "src/main.ts", "content": "class Test {}"}],
        "relevant_test_files": [{"file_path": "src/__tests__/main.test.ts", "content": "describe('Test', () => {});"}],
        "test_structure": {},
        "feedback": {}
    }

    # Invoke test chain directly
    generated_tests = agent.test_generation_chain.invoke(test_state)
    assert isinstance(generated_tests, str), "Chain should return string"
    assert len(generated_tests) > 0, "Generated tests should not be empty"
    assert "describe(" in generated_tests or "test(" in generated_tests, "Should generate test-like content"
    assert len(result["generated_tests"]) > 0