import pytest
import json
from unittest.mock import patch
from ticket_interpreter import fetch_issue, process_with_llm, State

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

# Expected JSON output for well-structured ticket
EXPECTED_WELL_STRUCTURED_JSON = {
    "title": "Implement Timestamp-based UUID Generator in Obsidian",
    "description": "Add a command to Obsidian that generates a UUID based on the current timestamp and inserts it into the active note.",
    "requirements": [
        "The command must be accessible via Obsidian's command palette.",
        "It should generate a UUID using the current timestamp, following the UUID v7 standard."
    ],
    "acceptance_criteria": [
        "The command is visible in Obsidian's command palette when searched.",
        "When the command is executed with an active note, a valid UUID v7 is generated and inserted."
    ]
}

# Sample sloppy ticket content
SLOPPY_TICKET = """
Need a UUID thing in Obsidian. Should add it to notes quick.
"""

# Mock LLM response for sloppy ticket
MOCK_LLM_RESPONSE = json.dumps({
    "title": "Add UUID Generator to Obsidian",
    "description": "Implement a feature to quickly add a UUID to notes in Obsidian.",
    "requirements": ["Should add UUID to notes quickly"],
    "acceptance_criteria": ["UUID is inserted into the note when triggered"]
})

@pytest.fixture
def mock_github_issue():
    class MockIssue:
        body = WELL_STRUCTURED_TICKET
    class MockRepo:
        def get_issue(self, number):
            return MockIssue()
    class MockGithub:
        def get_repo(self, repo_name):
            return MockRepo()
    return MockGithub()

def test_fetch_issue(mock_github_issue):
    with patch('ticket_interpreter.github', mock_github_issue):
        state = {"url": "https://github.com/user/repo/issues/1"}
        result = fetch_issue(state)
        assert result["ticket_content"] == WELL_STRUCTURED_TICKET

def test_process_with_llm_well_structured():
    with patch('ticket_interpreter.llm') as mock_llm:
        mock_llm.return_value = json.dumps(EXPECTED_WELL_STRUCTURED_JSON)
        state = {"ticket_content": WELL_STRUCTURED_TICKET}
        result = process_with_llm(state)
        assert result["result"] == EXPECTED_WELL_STRUCTURED_JSON

def test_process_with_llm_sloppy():
    with patch('ticket_interpreter.llm') as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE
        state = {"ticket_content": SLOPPY_TICKET}
        result = process_with_llm(state)
        assert result["result"] == json.loads(MOCK_LLM_RESPONSE)

def test_invalid_llm_response():
    with patch('ticket_interpreter.llm') as mock_llm, patch('sys.exit') as mock_exit:
        mock_llm.return_value = "Invalid JSON"
        state = {"ticket_content": WELL_STRUCTURED_TICKET}
        process_with_llm(state)
        mock_exit.assert_called_once_with(1)
