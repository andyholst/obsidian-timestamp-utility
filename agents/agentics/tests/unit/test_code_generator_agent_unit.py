import pytest
from src.code_generator_agent import CodeGeneratorAgent
from src.state import State
from src.agentics import llm

def test_code_generator_agent_valid_input():
    # Given: Structured ticket details
    agent = CodeGeneratorAgent(llm)
    state = State(result={
        "title": "Generate UUID",
        "description": "Create a UUID generator",
        "requirements": ["Use timestamp"],
        "acceptance_criteria": ["Valid UUID format"]
    })
    
    # When: Processing the ticket
    result = agent(state)
    
    # Then: Verify code and tests are generated
    assert "generated_code" in result, "Generated code missing"
    assert "generated_tests" in result, "Generated tests missing"
    assert isinstance(result["generated_code"], str), "Generated code should be a string"
    assert isinstance(result["generated_tests"], str), "Generated tests should be a string"
    assert "```typescript" in result["generated_code"], "Code should be in TypeScript markdown"
    assert "```typescript" in result["generated_tests"], "Tests should be in TypeScript markdown"
    assert "uuid" in result["generated_code"].lower(), "Generated code should mention UUID"

def test_code_generator_agent_missing_fields():
    # Given: Incomplete ticket details
    agent = CodeGeneratorAgent(llm)
    state = State(result={"title": "Generate UUID"})
    
    # When: Processing the ticket
    # Then: Expect a ValueError for missing fields
    with pytest.raises(ValueError, match="Missing field in state"):
        agent(state)

def test_code_generator_agent_empty_requirements():
    # Given: Ticket with empty requirements and criteria
    agent = CodeGeneratorAgent(llm)
    state = State(result={
        "title": "Minimal Task",
        "description": "Do something minimal",
        "requirements": [],
        "acceptance_criteria": []
    })
    
    # When: Processing the ticket
    result = agent(state)
    
    # Then: Verify minimal output is generated
    assert "generated_code" in result, "Generated code missing"
    assert "generated_tests" in result, "Generated tests missing"
    assert isinstance(result["generated_code"], str), "Generated code should be a string"
    assert isinstance(result["generated_tests"], str), "Generated tests should be a string"
