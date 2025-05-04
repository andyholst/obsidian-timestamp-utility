import pytest
import json
import os
import logging
from unittest.mock import patch, MagicMock
from src.agentics import (
    app,
    fetch_issue_agent,
    process_llm_agent,
    code_generator_agent,
    FetchIssueAgent,
    ProcessLLMAgent,
    CodeGeneratorAgent,
    OutputResultAgent,
    prompt_template
)
from src.pre_test_runner_agent import PreTestRunnerAgent
from src.utils import validate_github_url
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

# Test URL validation
def test_validate_github_url():
    assert validate_github_url("https://github.com/user/repo/issues/1") == True
    assert validate_github_url("https://github.com/user/repo/pull/1") == False
    assert validate_github_url("invalid_url") == False

# Test FetchIssueAgent with valid URL
def test_fetch_issue_agent():
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    agent = FetchIssueAgent(mock_github)
    state = {"url": "https://github.com/user/repo/issues/1"}
    result = agent(state)
    assert result["ticket_content"] == WELL_STRUCTURED_TICKET

# Test FetchIssueAgent with invalid URL
def test_fetch_issue_agent_invalid_url():
    mock_github = MagicMock()
    agent = FetchIssueAgent(mock_github)
    state = {"url": "invalid_url"}
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        agent(state)

# Test FetchIssueAgent with empty ticket content
def test_fetch_issue_agent_empty_content():
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = ""
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    agent = FetchIssueAgent(mock_github)
    state = {"url": "https://github.com/user/repo/issues/1"}
    with pytest.raises(ValueError, match="Empty ticket content"):
        agent(state)

# Test FetchIssueAgent with GitHub API error
def test_fetch_issue_agent_github_error():
    mock_github = MagicMock()
    mock_github.get_repo.side_effect = GithubException("Repo not found")
    agent = FetchIssueAgent(mock_github)
    state = {"url": "https://github.com/user/repo/issues/1"}
    with pytest.raises(GithubException):
        agent(state)

# Test ProcessLLMAgent with well-structured ticket
def test_process_llm_agent_well_structured():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = json.dumps(EXPECTED_TICKET_JSON)
    agent = ProcessLLMAgent(mock_llm, prompt_template)
    state = {"ticket_content": WELL_STRUCTURED_TICKET}
    result = agent(state)
    assert result["result"] == EXPECTED_TICKET_JSON

# Test ProcessLLMAgent with sloppy ticket
def test_process_llm_agent_sloppy():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = json.dumps(EXPECTED_TICKET_JSON)
    agent = ProcessLLMAgent(mock_llm, prompt_template)
    state = {"ticket_content": SLOPPY_TICKET}
    result = agent(state)
    assert result["result"] == EXPECTED_TICKET_JSON

# Test ProcessLLMAgent with invalid JSON response
def test_process_llm_agent_invalid_json():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = ["Invalid JSON", "Invalid JSON", "Invalid JSON"]
    agent = ProcessLLMAgent(mock_llm, prompt_template)
    state = {"ticket_content": WELL_STRUCTURED_TICKET}
    with pytest.raises(ValueError, match="Invalid LLM response"):
        agent(state)

# Test ProcessLLMAgent with invalid structure (missing fields)
def test_process_llm_agent_invalid_structure():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [INVALID_LLM_RESPONSE, INVALID_LLM_RESPONSE, INVALID_LLM_RESPONSE]
    agent = ProcessLLMAgent(mock_llm, prompt_template)
    state = {"ticket_content": WELL_STRUCTURED_TICKET}
    with pytest.raises(ValueError, match="Invalid LLM response"):
        agent(state)

# Test ProcessLLMAgent retry mechanism
def test_process_llm_agent_retry():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = ["Invalid JSON", json.dumps(EXPECTED_TICKET_JSON)]
    agent = ProcessLLMAgent(mock_llm, prompt_template)
    state = {"ticket_content": WELL_STRUCTURED_TICKET}
    result = agent(state)
    assert result["result"] == EXPECTED_TICKET_JSON
    assert mock_llm.invoke.call_count == 2

# Test OutputResultAgent
def test_output_result_agent(caplog):
    agent = OutputResultAgent()
    state = {"result": EXPECTED_TICKET_JSON}
    with caplog.at_level(logging.INFO):
        result = agent(state)
        assert "Final result:" in caplog.text
        assert json.dumps(EXPECTED_TICKET_JSON, indent=2) in caplog.text
        assert result == state

# Test CodeGeneratorAgent
def test_code_generator_agent():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        "// Generated TS code\n function generateUUID() { return 'uuid'; }",
        "// Generated tests\n test('UUID works', () => { expect(generateUUID()).toBe('uuid'); });"
    ]
    agent = CodeGeneratorAgent(mock_llm)
    state = {
        "result": {
            "title": "Test Title",
            "description": "Test Description",
            "requirements": ["Req1", "Req2"],
            "acceptance_criteria": ["AC1", "AC2"]
        }
    }
    result = agent(state)
    assert "generated_code" in result
    assert "generated_tests" in result
    assert result["generated_code"].strip() == "// Generated TS code\n function generateUUID() { return 'uuid'; }"
    assert result["generated_tests"].strip() == "// Generated tests\n test('UUID works', () => { expect(generateUUID()).toBe('uuid'); });"
    assert mock_llm.invoke.call_count == 2

# Test PreTestRunnerAgent - Success Case
@patch('subprocess.run')
def test_pre_test_runner_agent_success(mock_run):
    mock_install = MagicMock(returncode=0, stdout="", stderr="")
    mock_test = MagicMock(returncode=0, stdout="Tests: 20 passed, 20 total\nAll files | 46.15 | 50 | 33.33 | 46.15 |", stderr="")
    mock_run.side_effect = [mock_install, mock_test]
    agent = PreTestRunnerAgent()
    state = {}
    result = agent(state)
    assert result["existing_tests_passed"] == 20
    assert result["existing_coverage_all_files"] == 46.15

# Test PreTestRunnerAgent - Test Failure
@patch('subprocess.run')
def test_pre_test_runner_agent_failure(mock_run):
    mock_install = MagicMock(returncode=0, stdout="", stderr="")
    mock_test = MagicMock(returncode=1, stdout="", stderr="Test failed")
    mock_run.side_effect = [mock_install, mock_test]
    agent = PreTestRunnerAgent()
    state = {}
    with pytest.raises(RuntimeError, match="Existing tests failed. Please fix the tests before proceeding."):
        agent(state)

# Test PreTestRunnerAgent - Parsing Error
@patch('subprocess.run')
def test_pre_test_runner_agent_parsing_error(mock_run, caplog):
    mock_install = MagicMock(returncode=0, stdout="", stderr="")
    mock_test = MagicMock(returncode=0, stdout="Some random output", stderr="")
    mock_run.side_effect = [mock_install, mock_test]
    agent = PreTestRunnerAgent()
    state = {}
    with caplog.at_level(logging.WARNING):
        result = agent(state)
        assert "Could not find number of passing tests; defaulting to 0" in caplog.text
        assert "Could not parse coverage; defaulting to 0.0" in caplog.text
        assert result["existing_tests_passed"] == 0
        assert result["existing_coverage_all_files"] == 0.0

# Test full workflow with code generation and pre-test runner
def test_full_workflow_unit():
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = WELL_STRUCTURED_TICKET
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        json.dumps(EXPECTED_TICKET_JSON),
        "// Generated TS code\n function generateUUID() { return 'uuid'; }",
        "// Generated tests\n test('UUID works', () => { expect(generateUUID()).toBe('uuid'); });"
    ]

    with patch.object(fetch_issue_agent, 'github', mock_github), \
         patch.object(process_llm_agent, 'llm', mock_llm), \
         patch.object(code_generator_agent, 'llm', mock_llm), \
         patch('subprocess.run') as mock_run:
        mock_install = MagicMock(returncode=0, stdout="", stderr="")
        mock_test = MagicMock(returncode=0, stdout="Tests: 20 passed, 20 total\nAll files | 46.15 | 50 | 33.33 | 46.15 |", stderr="")
        mock_run.side_effect = [mock_install, mock_test]
        initial_state = {"url": "https://github.com/user/repo/issues/1"}
        result = app.invoke(initial_state)
        assert "result" in result
        assert "generated_code" in result
        assert "generated_tests" in result
        assert "existing_tests_passed" in result
        assert "existing_coverage_all_files" in result
        assert result["result"] == EXPECTED_TICKET_JSON
        assert result["generated_code"].strip() == "// Generated TS code\n function generateUUID() { return 'uuid'; }"
        assert result["generated_tests"].strip() == "// Generated tests\n test('UUID works', () => { expect(generateUUID()).toBe('uuid'); });"
        assert result["existing_tests_passed"] == 20
        assert result["existing_coverage_all_files"] == 46.15

# Test full workflow with invalid URL
def test_full_workflow_invalid_url():
    initial_state = {"url": "invalid_url"}
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        app.invoke(initial_state)
