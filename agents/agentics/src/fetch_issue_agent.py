import logging
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from github import GithubException

from .base_agent import BaseAgent
from .state import State
from .utils import validate_github_url, log_info
from .clients import github

class FetchIssueAgent(BaseAgent):
    def __init__(self, github_client):
        super().__init__("FetchIssue")
        self.github = github_client
        self.monitor.setLevel(logging.INFO)
        log_info(self.name, "Initialized FetchIssueAgent")

    def process(self, state: State) -> State:
        """Fetch GitHub issue content based on the provided URL and update the state."""
        log_info(self.name, f"Before processing in {self.name}: processing completed")
        log_info(self.name, "Starting issue fetch process")
        url = state['url']
        log_info(self.name, f"Processing GitHub URL: {url}")
        if not validate_github_url(url):
            self.monitor.error("Invalid GitHub URL provided")
            raise ValueError("Invalid GitHub URL")
        parts = url.split('/')
        owner, repo, issue_number = parts[3], parts[4], int(parts[6])
        log_info(self.name, f"Parsed URL components - owner: {owner}, repo: {repo}, issue_number: {issue_number}")
        # Ensure github client is available
        if not self.github:
            from .services import get_service_manager
            self.github = get_service_manager().github

        log_info(self.name, f"Initializing GitHub API connection for {owner}/{repo}")
        repo_obj = self.github.get_repo(f"{owner}/{repo}")
        log_info(self.name, f"Successfully connected to repository {owner}/{repo}")

        log_info(self.name, f"Fetching issue #{issue_number}")
        issue = repo_obj.get_issue(issue_number)
        log_info(self.name, f"Issue #{issue_number} fetched successfully - title: {issue.title}")

        if not issue.body:
            log_info(self.name, "Issue body is empty")
            raise ValueError("Empty ticket content")

        ticket_content = issue.body
        log_info(self.name, f"Issue body length: {len(ticket_content)} characters")
        log_info(self.name, f"Issue body preview: {ticket_content[:200]}...")

        state['ticket_content'] = ticket_content
        log_info(self.name, "Ticket content stored in state")
        log_info(self.name, "Issue fetch process completed successfully")
        log_info(self.name, f"After processing in {self.name}: processing completed")
        return state
