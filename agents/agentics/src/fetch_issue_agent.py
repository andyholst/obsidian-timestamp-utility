from .base_agent import BaseAgent
from .state import State
from .utils import validate_github_url

class FetchIssueAgent(BaseAgent):
    def __init__(self, github_client):
        super().__init__("FetchIssue")
        self.github = github_client

    def process(self, state: State) -> State:
        url = state['url']
        if not validate_github_url(url):
            raise ValueError("Invalid GitHub URL")
        parts = url.split('/')
        owner, repo, issue_number = parts[3], parts[4], int(parts[6])
        repo = self.github.get_repo(f"{owner}/{repo}")
        issue = repo.get_issue(issue_number)
        if not issue.body:
            raise ValueError("Empty ticket content")
        state['ticket_content'] = issue.body
        return state
