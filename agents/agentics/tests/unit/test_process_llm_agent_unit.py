import pytest
import json
import os
from src.process_llm_agent import ProcessLLMAgent
from src.state import State
from src.agentics import llm, prompt_template

# Well-structured ticket content
WELL_STRUCTURED_TICKET = """
# Implement Timestamp-based UUID Generator in Obsidian

## Description
Add a command to Obsidian that generates a UUID (Universally Unique Identifier) based on the current timestamp and inserts it into the active note at the cursor position. This feature will allow users to quickly create unique identifiers for linking, referencing, or organizing content within their notes. The UUID should follow the UUID v7 standard, which is the latest version, offering improved performance and privacy over earlier versions like UUID v1.

## Requirements
- The command must be accessible via Obsidian's command palette.
- It should generate a UUID using the current timestamp, following the UUID v7 standard.
- The generated UUID must be inserted at the current cursor position in the active note.
- If no note is active when the command is executed, an appropriate error message should be displayed.

## Acceptance Criteria
- The command is visible in Obsidian's command palette when searched.
- When the command is executed with an active note, a valid UUID v7 is generated and inserted at the cursor position.
- The generated UUID is unique and correctly formatted according to the UUID v7 standard.
- If no note is active when the command is executed, an error message is displayed to the user.
"""

# Sloppy ticket content
SLOPPY_TICKET = """
Implement Timestamp-based UUID Generator in Obsidian

Add a command to Obsidian that generates a UUID (Universally Unique Identifier) based on the current timestamp and inserts it into the active note at the cursor position. This feature will allow users to quickly create unique identifiers for linking, referencing, or organizing content within their notes. The UUID should follow the UUID v7 standard, which is the latest version, offering improved performance and privacy over earlier versions like UUID v1.

The command must be accessible via Obsidian's command palette.
It should generate a UUID using the current timestamp, following the UUID v7 standard.
The generated UUID must be inserted at the current cursor position in the active note.
If no note is active when the command is executed, an appropriate error message should be displayed.

When this is considering done

The command is visible in Obsidian's command palette when searched.
When the command is executed with an active note, a valid UUID v7 is generated and inserted at the cursor position.
The generated UUID is unique and correctly formatted according to the UUID v7 standard.
If no note is active when the command is executed, an error message is displayed to the user.
"""

# Long ticket content (for variety, though not explicitly provided, keeping it simple)
LONG_TICKET = "# Very Long Ticket Title\n" + "Description with lots of details " * 50 + "\n- Req1\n- Req2\n- AC1\n- AC2"

# Expected JSON for long ticket (simplified for testing purposes)
EXPECTED_LONG_JSON = {
    "title": "# Very Long Ticket Title",
    "description": "Description with lots of details " * 50,
    "requirements": ["Req1", "Req2"],
    "acceptance_criteria": ["AC1", "AC2"]
}

# Fixture to load expected JSON from file for well-structured and sloppy tickets
@pytest.fixture
def expected_ticket_json():
    """Load the expected JSON for well-structured and sloppy tickets from a file."""
    expected_json_path = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'expected_ticket.json')
    with open(expected_json_path, 'r') as f:
        return json.load(f)

def test_process_llm_agent_well_structured(expected_ticket_json):
    """Test processing a well-structured ticket with real LLM."""
    agent = ProcessLLMAgent(llm, prompt_template)
    state = State(ticket_content=WELL_STRUCTURED_TICKET)
    
    # When: Processing the ticket with the real LLM
    result = agent(state)
    
    # Then: Verify the structure and key content
    assert "result" in result, "Result key missing"
    assert isinstance(result["result"], dict), "Result should be a dictionary"
    assert all(key in result["result"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"
    assert isinstance(result["result"]["requirements"], list), "Requirements should be a list"
    assert isinstance(result["result"]["acceptance_criteria"], list), "Acceptance criteria should be a list"
    assert "UUID" in result["result"]["description"], "Description should mention UUID"
    assert len(result["result"]["requirements"]) >= 1, "Should have at least one requirement"
    assert len(result["result"]["acceptance_criteria"]) >= 1, "Should have at least one criterion"

def test_process_llm_agent_sloppy(expected_ticket_json):
    """Test processing a sloppy ticket with real LLM."""
    agent = ProcessLLMAgent(llm, prompt_template)
    state = State(ticket_content=SLOPPY_TICKET)
    
    # When: Processing the ticket with the real LLM
    result = agent(state)
    
    # Then: Verify the structure and key content
    assert "result" in result, "Result key missing"
    assert isinstance(result["result"], dict), "Result should be a dictionary"
    assert all(key in result["result"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"
    assert isinstance(result["result"]["requirements"], list), "Requirements should be a list"
    assert isinstance(result["result"]["acceptance_criteria"], list), "Acceptance criteria should be a list"
    assert "UUID" in result["result"]["description"], "Description should mention UUID"
    assert len(result["result"]["requirements"]) >= 3, "Should have at least three requirements based on ticket"
    assert len(result["result"]["acceptance_criteria"]) >= 3, "Should have at least three criteria based on ticket"

def test_process_llm_agent_long_ticket():
    """Test processing a long ticket with real LLM."""
    agent = ProcessLLMAgent(llm, prompt_template)
    state = State(ticket_content=LONG_TICKET)
    
    # When: Processing the ticket with the real LLM
    result = agent(state)
    
    # Then: Verify the structure and key content
    assert "result" in result, "Result key missing"
    assert isinstance(result["result"], dict), "Result should be a dictionary"
    assert all(key in result["result"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"
    assert isinstance(result["result"]["requirements"], list), "Requirements should be a list"
    assert isinstance(result["result"]["acceptance_criteria"], list), "Acceptance criteria should be a list"
    assert result["result"]["title"] == "# Very Long Ticket Title", "Title should match"
    assert len(result["result"]["description"]) > 0, "Description should be non-empty"
    assert len(result["result"]["requirements"]) >= 2, "Should have at least two requirements"
    assert len(result["result"]["acceptance_criteria"]) >= 2, "Should have at least two criteria"

def test_process_llm_agent_invalid_json(expected_ticket_json):
    """Test handling of invalid JSON response from real LLM (assuming it could happen)."""
    agent = ProcessLLMAgent(llm, prompt_template)
    state = State(ticket_content=WELL_STRUCTURED_TICKET)
    
    # When/Then: Process normally, assuming retries handle invalid JSON
    result = agent(state)
    assert "result" in result, "Result key missing"
    assert isinstance(result["result"], dict), "Result should be a dictionary"
    assert all(key in result["result"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"

def test_process_llm_agent_invalid_structure(expected_ticket_json):
    """Test handling of invalid structure from real LLM."""
    agent = ProcessLLMAgent(llm, prompt_template)
    state = State(ticket_content=WELL_STRUCTURED_TICKET)
    
    # When/Then: Process normally, assuming retries handle invalid structure
    result = agent(state)
    assert "result" in result, "Result key missing"
    assert isinstance(result["result"], dict), "Result should be a dictionary"
    assert all(key in result["result"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"

def test_process_llm_agent_invalid_types(expected_ticket_json):
    """Test handling of invalid types from real LLM."""
    agent = ProcessLLMAgent(llm, prompt_template)
    state = State(ticket_content=WELL_STRUCTURED_TICKET)
    
    # When/Then: Process normally, assuming retries handle invalid types
    result = agent(state)
    assert "result" in result, "Result key missing"
    assert isinstance(result["result"], dict), "Result should be a dictionary"
    assert all(key in result["result"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"
    assert isinstance(result["result"]["requirements"], list), "Requirements should be a list"
    assert isinstance(result["result"]["acceptance_criteria"], list), "Acceptance criteria should be a list"

def test_process_llm_agent_retry_success(expected_ticket_json):
    """Test that the agent succeeds after potential retries with real LLM."""
    agent = ProcessLLMAgent(llm, prompt_template)
    state = State(ticket_content=WELL_STRUCTURED_TICKET)
    
    # When: Processing the ticket with the real LLM
    result = agent(state)
    
    # Then: Verify the structure and key content
    assert "result" in result, "Result key missing"
    assert isinstance(result["result"], dict), "Result should be a dictionary"
    assert all(key in result["result"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"
    assert isinstance(result["result"]["requirements"], list), "Requirements should be a list"
    assert isinstance(result["result"]["acceptance_criteria"], list), "Acceptance criteria should be a list"
    assert "UUID" in result["result"]["description"], "Description should mention UUID"
    assert len(result["result"]["requirements"]) >= 1, "Should have at least one requirement"
    assert len(result["result"]["acceptance_criteria"]) >= 1, "Should have at least one criterion"

def test_process_llm_agent_dict_input():
    # Given: A state with refined_ticket as a dict
    agent = ProcessLLMAgent(llm, prompt_template)
    state = State(refined_ticket={
        "title": "Test Ticket",
        "description": "Test description",
        "requirements": ["Req1"],
        "acceptance_criteria": ["AC1"]
    })
    
    # When: Processing the ticket with real LLM
    result = agent(state)
    
    # Then: Verify dict is processed correctly
    assert "result" in result, "Result key missing"
    assert isinstance(result["result"], dict), "Result should be a dictionary"
    assert all(key in result["result"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"
    assert result["result"]["title"] == "Test Ticket", "Title should match input"

# New test: Empty ticket content
def test_process_llm_agent_empty_ticket():
    agent = ProcessLLMAgent(llm, prompt_template)
    state = State(ticket_content="")
    
    # When: Processing the ticket with real LLM
    result = agent(state)
    
    # Then: Verify minimal valid output
    assert "result" in result, "Result key missing"
    assert isinstance(result["result"], dict), "Result should be a dictionary"
    assert all(key in result["result"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"
    assert isinstance(result["result"]["requirements"], list), "Requirements should be a list"
    assert isinstance(result["result"]["acceptance_criteria"], list), "Acceptance criteria should be a list"
    assert len(result["result"]["title"]) > 0, "Title should be generated"

# New test: Malformed ticket causing potential invalid JSON
def test_process_llm_agent_malformed_ticket():
    agent = ProcessLLMAgent(llm, prompt_template)
    state = State(ticket_content="# Title\n{unclosed bracket\n- Req1")
    
    # When: Processing the ticket with real LLM
    result = agent(state)
    
    # Then: Verify agent handles it gracefully
    assert "result" in result, "Result key missing"
    assert isinstance(result["result"], dict), "Result should be a dictionary"
    assert all(key in result["result"] for key in ["title", "description", "requirements", "acceptance_criteria"]), "Missing required fields"
