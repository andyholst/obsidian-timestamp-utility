# fetch_issue_agent.py
import logging
import json
from typing import Dict, Any
from .base_agent import BaseAgent
from .state import State
from .utils import validate_github_url, log_info

class FetchIssueAgent(BaseAgent):
    def __init__(self, github_client):
        super().__init__("FetchIssue")
        self.github = github_client
        self.logger.setLevel(logging.INFO)

    def process(self, state: State) -> State:
        url = state['url']
        if not validate_github_url(url):
            raise ValueError("Invalid GitHub URL")
        parts = url.split('/')
        owner, repo, issue_number = parts[3], parts[4], int(parts[6])
        repo_obj = self.github.get_repo(f"{owner}/{repo}")
        issue = repo_obj.get_issue(issue_number)
        if not issue.body:
            raise ValueError("Empty ticket content")
        state['ticket_content'] = issue.body
        return state
