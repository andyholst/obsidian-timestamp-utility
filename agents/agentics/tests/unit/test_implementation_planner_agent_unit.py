import pytest
from unittest.mock import MagicMock
from src.implementation_planner_agent import ImplementationPlannerAgent
from src.state import State
from src.clients import llm_reasoning as llm

def test_implementation_planner_agent():
    # Given: Mocked LLM and refined ticket
    agent = ImplementationPlannerAgent(llm)
    state = State(
        url="https://github.com/user/repo/issues/1",
        ticket_content="Implement UUID generation",
        refined_ticket={
            "title": "Implement UUID Generation",
            "description": "Add functionality to generate UUIDs",
            "requirements": ["Generate UUID v7"],
            "acceptance_criteria": ["UUID is generated correctly"]
        }
    )

    # When: Processing the refined ticket
    result = agent(state)

    # Then: Verify enhanced ticket with implementation details
    assert "refined_ticket" in result, "Refined ticket missing"
    enhanced = result["refined_ticket"]
    assert all(key in enhanced for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"
    assert "implementation_steps" in enhanced, "Implementation steps missing"
    assert "npm_packages" in enhanced, "NPM packages missing"
    assert "manual_implementation_notes" in enhanced, "Manual implementation notes missing"
    assert isinstance(enhanced["implementation_steps"], list), "Implementation steps should be a list"
    assert isinstance(enhanced["npm_packages"], list), "NPM packages should be a list"
    assert len(enhanced["implementation_steps"]) > 0, "Implementation steps should not be empty"
    assert len(enhanced["npm_packages"]) >= 0, "NPM packages can be empty but should be a list"
    assert isinstance(enhanced["manual_implementation_notes"], str), "Manual implementation notes should be a string"
    # Check that original fields are preserved
    assert enhanced["title"] == "Implement UUID Generation", "Title should be preserved"
    assert enhanced["description"] == "Add functionality to generate UUIDs", "Description should be preserved"
    assert enhanced["requirements"] == ["Generate UUID v7"], "Requirements should be preserved"
    assert enhanced["acceptance_criteria"] == ["UUID is generated correctly"], "Acceptance criteria should be preserved"
    # Check that new fields are added
    if enhanced["npm_packages"]:
        if isinstance(enhanced["npm_packages"][0], dict):
            npm_names = [pkg['name'] for pkg in enhanced["npm_packages"]]
        else:
            npm_names = enhanced["npm_packages"]
        assert "uuid" in " ".join(npm_names).lower(), "NPM packages should include uuid-related package"
    assert any("uuid" in step.lower() for step in enhanced["implementation_steps"]), "Implementation steps should mention UUID"

def test_implementation_planner_agent_no_npm_needed():
    # Given: Ticket that might not need npm packages
    agent = ImplementationPlannerAgent(llm)
    state = State(
        url="https://github.com/user/repo/issues/1",
        ticket_content="Add a simple console log",
        refined_ticket={
            "title": "Add Console Log",
            "description": "Add a simple console.log statement",
            "requirements": ["Log a message to console"],
            "acceptance_criteria": ["Message is logged"]
        }
    )

    # When: Processing the refined ticket
    result = agent(state)

    # Then: Verify enhanced ticket
    assert "refined_ticket" in result
    enhanced = result["refined_ticket"]
    assert "implementation_steps" in enhanced
    assert "npm_packages" in enhanced
    assert "manual_implementation_notes" in enhanced
    assert isinstance(enhanced["implementation_steps"], list)
    assert isinstance(enhanced["npm_packages"], list)
    # For simple tasks, npm_packages might be empty
    assert len(enhanced["implementation_steps"]) > 0

def test_implementation_planner_agent_complex_ticket():
    # Given: More complex ticket
    agent = ImplementationPlannerAgent(llm)
    state = State(
        url="https://github.com/user/repo/issues/1",
        ticket_content="Implement file upload with progress",
        refined_ticket={
            "title": "Implement File Upload with Progress",
            "description": "Add file upload functionality with progress bar",
            "requirements": ["Handle file selection", "Show upload progress", "Handle errors"],
            "acceptance_criteria": ["File uploads successfully", "Progress is shown", "Errors are handled"]
        }
    )

    # When: Processing the refined ticket
    result = agent(state)

    # Then: Verify enhanced ticket has detailed implementation
    assert "refined_ticket" in result
    enhanced = result["refined_ticket"]
    assert "implementation_steps" in enhanced
    assert "npm_packages" in enhanced
    assert "manual_implementation_notes" in enhanced
    assert len(enhanced["implementation_steps"]) > 0
    # Complex tasks might suggest more packages
    assert isinstance(enhanced["npm_packages"], list)
