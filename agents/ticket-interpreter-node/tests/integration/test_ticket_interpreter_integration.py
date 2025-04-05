import pytest
import os
import json
from ticket_interpreter import app
from github import GithubException

# Define paths to the fixtures directory and JSON file
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '../fixtures')
EXPECTED_TICKET_JSON_FILE = os.path.join(FIXTURES_DIR, 'expected_ticket.json')

# Load expected JSON from file
with open(EXPECTED_TICKET_JSON_FILE, 'r') as f:
    EXPECTED_TICKET_JSON = json.load(f)

# Integration tests for the ticket interpreter workflow
# These tests use real GitHub API and LLM service calls.

@pytest.mark.integration
def test_full_workflow_well_structured():
    """Test the full workflow with a well-structured ticket."""
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/20"
    initial_state = {"url": test_url}
    result = app.invoke(initial_state)
    assert "result" in result
    assert result["result"] == EXPECTED_TICKET_JSON

@pytest.mark.integration
def test_full_workflow_sloppy():
    """Test the full workflow with a sloppy ticket."""
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/22"
    initial_state = {"url": test_url}
    result = app.invoke(initial_state)
    assert "result" in result
    assert result["result"] == EXPECTED_TICKET_JSON

@pytest.mark.integration
def test_empty_ticket():
    """Test the workflow with an empty ticket."""
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    test_url = f"{test_repo_url}/issues/23"
    initial_state = {"url": test_url}
    with pytest.raises(ValueError, match="Empty ticket content"):
        app.invoke(initial_state)

@pytest.mark.integration
def test_invalid_url():
    """Test the workflow with an invalid GitHub URL."""
    invalid_url = "https://github.com/user/repo/pull/1"
    initial_state = {"url": invalid_url}
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        app.invoke(initial_state)

@pytest.mark.integration
def test_non_existent_issue():
    """Test the workflow with a non-existent issue."""
    test_repo_url = os.getenv("TEST_ISSUE_URL")
    assert test_repo_url is not None, "TEST_ISSUE_URL environment variable is required"
    non_existent_url = f"{test_repo_url}/issues/99999"
    initial_state = {"url": non_existent_url}
    with pytest.raises(GithubException):
        app.invoke(initial_state)

@pytest.mark.integration
def test_non_existent_repo():
    """Test the workflow with a non-existent repository."""
    non_existent_url = "https://github.com/nonexistentuser/nonexistentrepo/issues/1"
    initial_state = {"url": non_existent_url}
    with pytest.raises(GithubException):
        app.invoke(initial_state)
