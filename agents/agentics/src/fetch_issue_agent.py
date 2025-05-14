import logging
import json

from .base_agent import BaseAgent
from .state import State
from .utils import validate_github_url, log_info

class FetchIssueAgent(BaseAgent):
    def __init__(self, github_client):
        super().__init__("FetchIssue")
        self.github = github_client
        self.logger.setLevel(logging.INFO)
        log_info(self.logger, "Initialized FetchIssueAgent with GitHub client")

    def process(self, state: State) -> State:
        """Fetch GitHub issue content based on the provided URL and update the state."""
        log_info(self.logger, f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        log_info(self.logger, "Starting issue fetch process")
        url = state['url']
        log_info(self.logger, f"Processing GitHub URL: {url}")
        if not validate_github_url(url):
            self.logger.error("Invalid GitHub URL provided")
            raise ValueError("Invalid GitHub URL")
        parts = url.split('/')
        owner, repo, issue_number = parts[3], parts[4], int(parts[6])
        log_info(self.logger, f"Extracted owner: {owner}, repo: {repo}, issue_number: {issue_number}")
        try:
            log_info(self.logger, f"Fetching repository: {owner}/{repo}")
            repo = self.github.get_repo(f"{owner}/{repo}")
            log_info(self.logger, f"Fetching issue #{issue_number}")
            issue = repo.get_issue(issue_number)
            if not issue.body:
                self.logger.error("Issue has empty content")
                raise ValueError("Empty ticket content")
            state['ticket_content'] = issue.body
            log_info(self.logger, f"Ticket content fetched: {issue.body}")
            log_info(self.logger, "Issue fetch process completed successfully")
            log_info(self.logger, f"After processing in {self.name}: {json.dumps(state, indent=2)}")
            return state
        except Exception as e:
            self.logger.error(f"Failed to fetch issue: {str(e)}")
            raise
