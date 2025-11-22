"""
Standardized mock GitHub responses for consistent testing.
These mocks provide realistic GitHub API responses to prevent LLM parsing issues.
"""

from unittest.mock import MagicMock
import json


def create_realistic_github_issue_mock(title="Test Issue", body="Test body", number=1, state="open", user="testuser", repo="test/repo"):
    """Create a realistic GitHub issue mock with all expected attributes."""

    # Mock user
    mock_user = MagicMock()
    mock_user.login = user
    mock_user.id = 12345
    mock_user.type = "User"

    # Mock repository
    mock_repo = MagicMock()
    mock_repo.full_name = repo
    mock_repo.name = repo.split('/')[1]
    mock_repo.owner = mock_user

    # Mock issue with comprehensive attributes
    mock_issue = MagicMock()
    mock_issue.number = number
    mock_issue.title = title
    mock_issue.body = body
    mock_issue.state = state
    mock_issue.user = mock_user
    mock_issue.created_at = "2024-01-01T00:00:00Z"
    mock_issue.updated_at = "2024-01-01T00:00:00Z"
    mock_issue.closed_at = None
    mock_issue.labels = []
    mock_issue.assignees = []
    mock_issue.milestone = None
    mock_issue.comments = 0
    mock_issue.html_url = f"https://github.com/{repo}/issues/{number}"
    mock_issue.repository = mock_repo

    # Mock repository methods
    mock_repo.get_issue.return_value = mock_issue

    return mock_issue, mock_repo


def create_well_structured_ticket_mock():
    """Create a mock for a well-structured GitHub issue."""
    body = """# Implement Timestamp-based UUID Generator in Obsidian

## Description
Add a command to Obsidian that generates a UUID based on the current timestamp and inserts it into the active note at the cursor position. This feature will allow users to quickly create unique identifiers for linking, referencing, or organizing content within their notes.

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

## Implementation Notes
This should integrate with the existing TimestampPlugin class and follow the established patterns for command registration and error handling."""

    return create_realistic_github_issue_mock(
        title="Implement Timestamp-based UUID Generator in Obsidian",
        body=body,
        number=1
    )


def create_unclear_ticket_mock():
    """Create a mock for an unclear/vague GitHub issue."""
    body = """# Do something

## Description
Make it better.

## Requirements
- It should work.

## Acceptance Criteria
- It works."""

    return create_realistic_github_issue_mock(
        title="Do something",
        body=body,
        number=2
    )


def create_malformed_ticket_mock():
    """Create a mock for a malformed GitHub issue."""
    body = """# Title Missing Closing Bracket
## Description
Add a feature with mismatched brackets: { { {.
## Requirements
- Do stuff with errors
## Acceptance Criteria
- It should somehow work"""

    return create_realistic_github_issue_mock(
        title="Title Missing Closing Bracket",
        body=body,
        number=3
    )


def create_empty_ticket_mock():
    """Create a mock for an empty GitHub issue."""
    return create_realistic_github_issue_mock(
        title="Empty Issue",
        body="",
        number=4
    )


def create_large_ticket_mock():
    """Create a mock for a large/complex GitHub issue."""
    body = "# Large Complex Ticket\n" + "Description " * 500 + "\n\n## Requirements\n- Req1\n- Req2\n- Req3\n\n## Acceptance Criteria\n- AC1\n- AC2\n- AC3"

    return create_realistic_github_issue_mock(
        title="Large Complex Ticket",
        body=body,
        number=5
    )


def create_github_repo_mock(owner="testuser", name="test-repo"):
    """Create a realistic GitHub repository mock."""
    mock_repo = MagicMock()
    mock_repo.full_name = f"{owner}/{name}"
    mock_repo.name = name
    mock_repo.owner.login = owner
    mock_repo.private = False
    mock_repo.fork = False
    mock_repo.language = "TypeScript"

    return mock_repo


def create_github_client_mock():
    """Create a complete GitHub client mock with realistic responses."""
    mock_client = MagicMock()

    # Mock user
    mock_user = MagicMock()
    mock_user.login = "testuser"
    mock_user.id = 12345
    mock_user.type = "User"

    # Mock repo
    mock_repo = create_github_repo_mock()

    # Mock issues
    well_structured_issue, _ = create_well_structured_ticket_mock()
    unclear_issue, _ = create_unclear_ticket_mock()
    malformed_issue, _ = create_malformed_ticket_mock()
    empty_issue, _ = create_empty_ticket_mock()
    large_issue, _ = create_large_ticket_mock()

    # Set up return values
    mock_client.get_user.return_value = mock_user
    mock_client.get_repo.return_value = mock_repo

    # Mock issue retrieval based on number
    def mock_get_issue(number):
        issues = {
            1: well_structured_issue,
            2: unclear_issue,
            3: malformed_issue,
            4: empty_issue,
            5: large_issue
        }
        return issues.get(number, well_structured_issue)

    mock_repo.get_issue.side_effect = mock_get_issue

    return mock_client


def create_github_error_responses():
    """Create mock GitHub error responses for testing error handling."""

    # Rate limiting error
    rate_limit_error = MagicMock()
    rate_limit_error.status = 403
    rate_limit_error.data = {"message": "API rate limit exceeded for user ID 12345."}
    rate_limit_error.headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1640995200"}

    # Authentication error
    auth_error = MagicMock()
    auth_error.status = 401
    auth_error.data = {"message": "Bad credentials"}

    # Not found error
    not_found_error = MagicMock()
    not_found_error.status = 404
    not_found_error.data = {"message": "Not Found"}

    # Server error
    server_error = MagicMock()
    server_error.status = 500
    server_error.data = {"message": "Internal server error"}

    return {
        "rate_limit": rate_limit_error,
        "auth": auth_error,
        "not_found": not_found_error,
        "server": server_error
    }


def create_github_client_with_errors():
    """Create a GitHub client mock that can simulate various error conditions."""
    mock_client = MagicMock()

    # Mock user
    mock_user = MagicMock()
    mock_user.login = "testuser"
    mock_user.id = 12345
    mock_user.type = "User"

    # Mock repo
    mock_repo = MagicMock()
    mock_repo.full_name = "test/repo"
    mock_repo.name = "repo"
    mock_repo.get_issue.return_value = MagicMock(
        number=1,
        title="Test Issue",
        body="Test body",
        state="open"
    )

    # Set up return values
    mock_client.get_user.return_value = mock_user
    mock_client.get_repo.return_value = mock_repo

    # Add error simulation methods
    def simulate_rate_limit():
        from github.GithubException import GithubException
        raise GithubException(403, {"message": "API rate limit exceeded"})

    def simulate_auth_error():
        from github.GithubException import GithubException
        raise GithubException(401, {"message": "Bad credentials"})

    def simulate_not_found():
        from github.GithubException import GithubException
        raise GithubException(404, {"message": "Not Found"})

    mock_client.simulate_rate_limit = simulate_rate_limit
    mock_client.simulate_auth_error = simulate_auth_error
    mock_client.simulate_not_found = simulate_not_found

    return mock_client


def create_github_paginated_responses():
    """Create mock responses for paginated GitHub API calls."""
    # Mock paginated issues
    issues_page_1 = [
        MagicMock(number=1, title="Issue 1", state="open"),
        MagicMock(number=2, title="Issue 2", state="closed"),
        MagicMock(number=3, title="Issue 3", state="open")
    ]

    issues_page_2 = [
        MagicMock(number=4, title="Issue 4", state="open"),
        MagicMock(number=5, title="Issue 5", state="closed")
    ]

    # Mock repository with pagination
    mock_repo = MagicMock()
    mock_repo.full_name = "test/repo"
    mock_repo.name = "repo"

    # Mock paginated get_issues method
    def mock_get_issues(state="open", sort="created", direction="desc", since=None):
        if state == "open":
            return issues_page_1 + issues_page_2
        elif state == "closed":
            return [issues_page_2[1]]  # Only closed issues
        return issues_page_1 + issues_page_2

    mock_repo.get_issues.side_effect = mock_get_issues

    return mock_repo, issues_page_1 + issues_page_2


def create_github_webhook_payloads():
    """Create mock GitHub webhook payloads for testing webhook handling."""
    issue_opened = {
        "action": "opened",
        "issue": {
            "number": 1,
            "title": "Test Issue",
            "body": "Test issue body",
            "state": "open",
            "user": {"login": "testuser", "id": 12345}
        },
        "repository": {
            "full_name": "test/repo",
            "name": "repo",
            "owner": {"login": "testuser"}
        }
    }

    issue_closed = {
        "action": "closed",
        "issue": {
            "number": 1,
            "title": "Test Issue",
            "body": "Test issue body",
            "state": "closed",
            "user": {"login": "testuser", "id": 12345}
        },
        "repository": {
            "full_name": "test/repo",
            "name": "repo",
            "owner": {"login": "testuser"}
        }
    }

    pr_opened = {
        "action": "opened",
        "pull_request": {
            "number": 1,
            "title": "Test PR",
            "body": "Test PR body",
            "state": "open",
            "user": {"login": "testuser", "id": 12345}
        },
        "repository": {
            "full_name": "test/repo",
            "name": "repo",
            "owner": {"login": "testuser"}
        }
    }

    return {
        "issue_opened": issue_opened,
        "issue_closed": issue_closed,
        "pr_opened": pr_opened
    }
    return mock_client