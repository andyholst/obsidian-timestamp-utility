import logging
import json
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from github import GithubException

from .base_agent import BaseAgent
from .state import State
from .utils import validate_github_url, log_info
from .clients import github
from .openspec_loader import (
    is_local_change_ref,
    load_change,
    create_change_from_issue,
)


class FetchIssueAgent(BaseAgent):
    def __init__(self, github_client):
        super().__init__("FetchIssue")
        self.github = github_client
        self.monitor.setLevel(logging.INFO)
        log_info(self.name, "Initialized FetchIssueAgent")

    def process(self, state: State) -> State:
        """Fetch issue content based on the provided URL and update the state.

        If the URL is a local OpenSpec change reference (e.g. ``openspec:<name>`` or a
        bare change-name slug), the content is loaded locally from
        ``openspec/changes/<name>`` instead of fetching from GitHub.
        """
        log_info(self.name, f"Before processing in {self.name}: processing completed")
        log_info(self.name, "Starting issue fetch process")
        url = state["url"]
        log_info(self.name, f"Processing URL: {url}")

        if is_local_change_ref(url):
            change_name = url.split(":", 1)[1] if ":" in url else url
            log_info(self.name, f"Local OpenSpec change reference detected: {change_name}")
            try:
                loaded = load_change(change_name)
            except FileNotFoundError as e:
                self.monitor.error(str(e))
                state["ticket_content"] = ""
                state["error"] = str(e)
                state["error_type"] = type(e).__name__
                return state
            state["ticket_content"] = loaded["ticket_content"]
            state["url"] = loaded["url"]
            log_info(
                self.name,
                f"Loaded local change '{change_name}' (body length {len(loaded['ticket_content'])}).",
            )
            return state

        if not validate_github_url(url):
            self.monitor.error("Invalid GitHub URL provided")
            raise ValueError("Invalid GitHub URL")
        parts = url.split("/")
        owner, repo, issue_number = parts[3], parts[4], int(parts[6])
        log_info(
            self.name,
            f"Parsed URL components - owner: {owner}, repo: {repo}, issue_number: {issue_number}",
        )
        # Ensure github client is available
        if not self.github:
            from .services import get_service_manager

            self.github = get_service_manager().github

        try:
            log_info(self.name, f"Initializing GitHub API connection for {owner}/{repo}")
            repo_obj = self.github.get_repo(f"{owner}/{repo}")
            log_info(self.name, f"Successfully connected to repository {owner}/{repo}")

            log_info(self.name, f"Fetching issue #{issue_number}")
            issue = repo_obj.get_issue(issue_number)
            log_info(
                self.name,
                f"Issue #{issue_number} fetched successfully - title: {issue.title}",
            )

            if not issue.body:
                log_info(self.name, "Issue body is empty")
                raise ValueError("Empty ticket content")

            ticket_content = issue.body
            log_info(self.name, f"Issue body length: {len(ticket_content)} characters")
            log_info(self.name, f"Issue body preview: {ticket_content[:200]}...")

            # Bridge to the local spec-driven workflow: seed a LOCAL OpenSpec change from this
            # fetched issue (via the OpenSpec CLI) so the rest of the pipeline runs offline
            # against `openspec:<change>` -- no further GitHub calls. If the change already
            # exists (idempotent), we reuse it. Generation then proceeds exactly like any
            # other local change (B3/B11: single source of truth).
            change_name = create_change_from_issue(
                url=url,
                issue_title=issue.title,
                issue_body=issue.body or "",
            )
            log_info(
                self.name,
                f"Seeded local OpenSpec change '{change_name}' from GitHub issue #{issue_number}.",
            )
            try:
                loaded = load_change(change_name)
            except FileNotFoundError as e:
                self.monitor.error(str(e))
                state["ticket_content"] = ""
                state["error"] = str(e)
                state["error_type"] = type(e).__name__
                return state
            state["ticket_content"] = loaded["ticket_content"]
            state["url"] = loaded["url"]
            log_info(
                self.name,
                f"Loaded local change '{change_name}' (body length {len(loaded['ticket_content'])}).",
            )
            return state
        except GithubException as e:
            log_info(self.name, f"GitHub API error: {str(e)}")
            state["ticket_content"] = ""
            state["error"] = f"GitHub API error: {str(e)}"
            state["error_type"] = type(e).__name__
            return state
        except Exception as e:
            log_info(self.name, f"Error fetching issue: {str(e)}")
            state["ticket_content"] = ""
            state["error"] = str(e)
            state["error_type"] = type(e).__name__
            return state
