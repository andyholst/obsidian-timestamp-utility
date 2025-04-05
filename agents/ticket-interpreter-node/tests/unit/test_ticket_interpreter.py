import pytest
import json
import os
from unittest.mock import patch, MagicMock
from ticket_interpreter import fetch_issue, process_with_llm, State, app, validate_github_url, validate_llm_response
from github import GithubException

# Define paths to the fixtures directory and JSON file
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '../fixtures')
EXPECTED_TICKET_JSON_FILE = os.path.join(FIXTURES_DIR, 'expected_ticket.json')

# Load expected JSON from file
with open(EXPECTED_TICKET_JSON_FILE, 'r') as f:
    EXPECTED_TICKET_JSON = json.load(f)

# Sample well-structured ticket content
WELL_STRUCTURED_TICKET = """
# Implement Timestamp-based UUID Generator in Obsidian

## Description
Add a command to Obsidian that generates a UUID based on the current timestamp and inserts it into the active note.

## Requirements
- The command must be accessible via Obsidian's command palette.
- It should generate a UUID using the current timestamp, following the UUID v7 standard.

## Acceptance Criteria
- The command is visible in Obsidian's command palette when searched.
- When the command is executed with an active note, a valid UUID v7 is generated and inserted.
"""

# Sample sloppy ticket content
SLOPPY_TICKET = """
Need a UUID thing in Obsidian. Should add it to notes quick.
"""

# Invalid LLM response (missing fields)
INVALID_LLM_RESPONSE = json.dumps({
    "title": "Incomplete Response",
    "description": "This response is missing requirements and acceptance criteria."
})

@pytest.fixture
def mock_github_issue():
    class MockIssue:
        def __init__(self, body):
            self.body = body
    class MockRepo:
        def get_issue(self, number):
            return MockIssue(WELL_STRUCTURED_TICKET)
    class MockGithub:
        def get_repo(self, repo_name):
            return MockRepo()
    return MockGithub()

# Test URL validation
def test_validate_github_url():
    assert validate_github_url("https://github.com/user/repo/issues/1") == True
    assert validate_github_url("https://github.com/user/repo/pull/1") == False
    assert validate_github_url("invalid_url") == False

# Test fetch_issue with valid URL
def test_fetch_issue(mock_github_issue):
    with patch('ticket_interpreter.github', mock_github_issue):
        state = {"url": "https://github.com/user/repo/issues/1"}
        result = fetch_issue(state)
        assert result["ticket_content"] == WELL_STRUCTURED_TICKET

# Test fetch_issue with invalid URL
def test_fetch_issue_invalid_url():
    state = {"url": "invalid_url"}
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        fetch_issue(state)

# Test fetch_issue with empty ticket content
def test_fetch_issue_empty_content(mock_github_issue):
    class MockIssue:
        body = ""
    class MockRepo:
        def get_issue(self, number):
            return MockIssue()
    class MockGithub:
        def get_repo(self, repo_name):
            return MockRepo()
    with patch('ticket_interpreter.github', MockGithub()):
        state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(ValueError, match="Empty ticket content"):
            fetch_issue(state)

# Test fetch_issue with GitHub API error
def test_fetch_issue_github_error(mock_github_issue):
    with patch('ticket_interpreter.github.get_repo', side_effect=GithubException("Repo not found")):
        state = {"url": "https://github.com/user/repo/issues/1"}
        with pytest.raises(GithubException):
            fetch_issue(state)

# Test process_with_llm with well-structured ticket
def test_process_with_llm_well_structured():
    with patch('ticket_interpreter.llm') as mock_llm:
        mock_llm.return_value = json.dumps(EXPECTED_TICKET_JSON)
        state = {"ticket_content": WELL_STRUCTURED_TICKET}
        result = process_with_llm(state)
        assert result["result"] == EXPECTED_TICKET_JSON

# Test process_with_llm with sloppy ticket
def test_process_with_llm_sloppy():
    with patch('ticket_interpreter.llm') as mock_llm:
        mock_llm.return_value = json.dumps(EXPECTED_TICKET_JSON)
        state = {"ticket_content": SLOPPY_TICKET}
        result = process_with_llm(state)
        assert result["result"] == EXPECTED_TICKET_JSON

# Test process_with_llm with invalid JSON response
def test_process_with_llm_invalid_json():
    with patch('ticket_interpreter.llm') as mock_llm:
        mock_llm.return_value = "Invalid JSON"
        state = {"ticket_content": WELL_STRUCTURED_TICKET}
        with pytest.raises(ValueError, match="Invalid LLM response"):
            process_with_llm(state)

# Test process_with_llm with invalid structure (missing fields)
def test_process_with_llm_invalid_structure():
    with patch('ticket_interpreter.llm') as mock_llm:
        mock_llm.return_value = INVALID_LLM_RESPONSE
        state = {"ticket_content": WELL_STRUCTURED_TICKET}
        with pytest.raises(ValueError, match="Invalid LLM response"):
            process_with_llm(state)

# Test process_with_llm retry mechanism
def test_process_with_llm_retry():
    with patch('ticket_interpreter.llm') as mock_llm:
        mock_llm.side_effect = ["Invalid JSON", json.dumps(EXPECTED_TICKET_JSON)]
        state = {"ticket_content": WELL_STRUCTURED_TICKET}
        result = process_with_llm(state)
        assert result["result"] == EXPECTED_TICKET_JSON
        assert mock_llm.call_count == 2

# Test full workflow
def test_full_workflow_unit(mock_github_issue):
    with patch('ticket_interpreter.github', mock_github_issue), \
         patch('ticket_interpreter.llm') as mock_llm:
        mock_llm.return_value = json.dumps(EXPECTED_TICKET_JSON)
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = app.invoke(initial_state)
        assert "result" in result
        assert result["result"] == EXPECTED_TICKET_JSON

# Test full workflow with invalid URL
def test_full_workflow_invalid_url():
    initial_state = {"url": "invalid_url"}
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        app.invoke(initial_state)
