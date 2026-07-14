import pytest
from unittest.mock import MagicMock, patch
from src.fetch_issue_agent import FetchIssueAgent
from src.state import State
from github import GithubException


def _mock_github_with_issue(body, issue_state="open"):
    """Build a mocked GitHub client whose get_repo(...).get_issue(...) returns `body`."""
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_issue.body = body
    mock_issue.state = issue_state
    mock_repo.get_issue.return_value = mock_issue
    mock_github.get_repo.return_value = mock_repo
    return mock_github


def test_fetch_issue_agent_valid_url():
    # Given: Mocked GitHub client with valid ticket. The agent now bridges to the local
    # spec-driven workflow (B15): it seeds `openspec:<change>` and loads THAT as the ticket
    # content. We mock the seed + load so the test stays deterministic (no real CLI writes).
    mock_github = _mock_github_with_issue("Sample ticket content")
    agent = FetchIssueAgent(mock_github)
    state = State(url="https://github.com/user/repo/issues/1")

    with patch(
        "src.fetch_issue_agent.create_change_from_issue", return_value="ticket1"
    ), patch(
        "src.fetch_issue_agent.load_change",
        return_value={"ticket_content": "Sample ticket content", "url": "openspec:ticket1"},
    ):
        # When: Processing the state
        result = agent(state)

    # Then: Verify ticket content is fetched via the seed-then-load bridge
    assert result["ticket_content"] == "Sample ticket content", "Expected ticket content"
    assert result["url"] == "openspec:ticket1", "URL should be re-pointed to the local change"
    mock_github.get_repo.assert_called_once_with("user/repo")
    mock_repo_get = mock_github.get_repo.return_value
    mock_repo_get.get_issue.assert_called_once_with(1)


def test_fetch_issue_agent_invalid_url():
    # Given: A URL that is NOT a local OpenSpec change ref (has a scheme) but is not
    # a valid GitHub issue URL. Note: bare slugs like "invalid_url" are now treated as
    # local change references by the agent and return an error state instead of raising.
    mock_github = MagicMock()
    agent = FetchIssueAgent(mock_github)
    state = State(url="https://example.com/not/a/github/issue")

    # When: Processing the state
    # Then: Expect a ValueError for the invalid GitHub URL
    with pytest.raises(ValueError, match="Invalid GitHub URL"):
        agent(state)


def test_fetch_issue_agent_empty_ticket():
    # Given: Mocked GitHub client with empty ticket
    mock_github = _mock_github_with_issue("")
    agent = FetchIssueAgent(mock_github)
    state = State(url="https://github.com/user/repo/issues/1")

    # When: Processing the state
    result = agent(state)

    # Then: Agent returns state with error info instead of raising
    assert result.get("error") is not None
    assert "Empty ticket content" in result.get("error", "")
    assert result.get("ticket_content") == ""


def test_fetch_issue_agent_github_error():
    # Given: Mocked GitHub client with error
    mock_github = MagicMock()
    mock_github.get_repo.side_effect = GithubException("Repo not found")
    agent = FetchIssueAgent(mock_github)
    state = State(url="https://github.com/user/repo/issues/1")

    # When: Processing the state
    result = agent(state)

    # Then: Agent returns state with error info instead of raising
    assert result.get("error") is not None
    assert result.get("error_type") == "GithubException"
    assert result.get("ticket_content") == ""


def test_fetch_issue_agent_closed_issue():
    # Given: Mocked GitHub client with closed issue. Like the valid-url case, the agent
    # seeds a local change and loads its content (B15 bridge). Mock the seed + load.
    mock_github = _mock_github_with_issue("Closed ticket content", issue_state="closed")
    agent = FetchIssueAgent(mock_github)
    state = State(url="https://github.com/user/repo/issues/1")

    with patch(
        "src.fetch_issue_agent.create_change_from_issue", return_value="ticket1"
    ), patch(
        "src.fetch_issue_agent.load_change",
        return_value={"ticket_content": "Closed ticket content", "url": "openspec:ticket1"},
    ):
        # When: Processing the state
        result = agent(state)

    # Then: Verify closed ticket content is fetched via the seed-then-load bridge
    assert result["ticket_content"] == "Closed ticket content", "Expected closed ticket content"
    assert result["url"] == "openspec:ticket1"
