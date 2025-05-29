import pytest
from unittest.mock import MagicMock
from src.fetch_issue_agent import FetchIssueAgent
from src.state import State
from github import GithubException

def test_fetch_issue_agent_valid_url():
    # Given: Mocked GitHub client with valid ticket
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = "Sample ticket content"
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    agent = FetchIssueAgent(mock_github)
    state = State(url="https://github.com/user/repo/issues/1")
    
    # When: Processing the state
    result = agent(state)
    
    # Then: Verify ticket content is fetched
    assert result["ticket_content"] == "Sample ticket content", "Expected ticket content"
    mock_github.get_repo.assert_called_once_with("user/repo")
    mock_repo.get_issue.assert_called_once_with(1)

def test_fetch_issue_agent_invalid_url():
    # Given: Invalid GitHub URL
    mock_github = MagicMock()
    agent = FetchIssueAgent(mock_github)
    state = State(url="invalid_url")
    
    # When: Processing the state
    # Then: Expect a ValueError
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        agent(state)

def test_fetch_issue_agent_empty_ticket():
    # Given: Mocked GitHub client with empty ticket
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = ""
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    agent = FetchIssueAgent(mock_github)
    state = State(url="https://github.com/user/repo/issues/1")
    
    # When: Processing the state
    # Then: Expect a ValueError
    with pytest.raises(ValueError, match="Empty ticket content"):
        agent(state)

def test_fetch_issue_agent_github_error():
    # Given: Mocked GitHub client with error
    mock_github = MagicMock()
    mock_github.get_repo.side_effect = GithubException("Repo not found")
    agent = FetchIssueAgent(mock_github)
    state = State(url="https://github.com/user/repo/issues/1")
    
    # When: Processing the state
    # Then: Expect a GithubException
    with pytest.raises(GithubException, match="Repo not found"):
        agent(state)

def test_fetch_issue_agent_closed_issue():
    # Given: Mocked GitHub client with closed issue
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = "Closed ticket content"
    mock_issue.state = "closed"
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    agent = FetchIssueAgent(mock_github)
    state = State(url="https://github.com/user/repo/issues/1")
    
    # When: Processing the state
    result = agent(state)
    
    # Then: Verify closed ticket content is fetched
    assert result["ticket_content"] == "Closed ticket content", "Expected closed ticket content"
