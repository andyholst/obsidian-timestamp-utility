import logging
import json

from .base_agent import BaseAgent
from .state import State
from .utils import validate_github_url

class FetchIssueAgent(BaseAgent):
    def __init__(self, github_client):
        super().__init__("FetchIssue")
        self.github = github_client
        self.logger.setLevel(logging.INFO)

    def process(self, state: State) -> State:
        self.logger.info(f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        self.logger.info("Starting issue fetch process")
        url = state['url']
        self.logger.info(f"Processing GitHub URL: {url}")
        if not validate_github_url(url):
            self.logger.error("Invalid GitHub URL provided")
            raise ValueError("Invalid GitHub URL")
        parts = url.split('/')
        owner, repo, issue_number = parts[3], parts[4], int(parts[6])
        self.logger.info(f"Extracted owner: {owner}, repo: {repo}, issue_number: {issue_number}")
        try:
            self.logger.info(f"Fetching repository: {owner}/{repo}")
            repo = self.github.get_repo(f"{owner}/{repo}")
            self.logger.info(f"Fetching issue #{issue_number}")
            issue = repo.get_issue(issue_number)
            if not issue.body:
                self.logger.error("Issue has empty content")
                raise ValueError("Empty ticket content")
            state['ticket_content'] = issue.body
            self.logger.info(f"Ticket content fetched: {issue.body}")
            self.logger.info("Issue fetch process completed successfully")
            self.logger.info(f"After processing in {self.name}: {json.dumps(state, indent=2)}")
            return state
        except Exception as e:
            self.logger.error(f"Failed to fetch issue: {str(e)}")
            raise
