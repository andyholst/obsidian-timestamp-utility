# ticket_clarity_agent.py
import json
import datetime
import re
import logging
from typing import Dict, Any
from .base_agent import BaseAgent
from .state import State
from langchain.prompts import PromptTemplate
from github import Github

class TicketClarityAgent(BaseAgent):
    def __init__(self, llm_client, github_client):
        super().__init__("TicketClarity")
        self.llm = llm_client
        self.github = github_client
        self.max_iterations = 2  # Reduced

    def evaluate_clarity(self, ticket_content: str) -> Dict[str, Any]:
        prompt = "/think\n" + PromptTemplate(
            input_variables=["ticket_content"],
            template=(
                "Evaluate clarity: JSON {'is_clear': bool, 'suggestions': list[str]}. Stick to facts; no assumptions. Only JSON.\n\n"
                "Ticket: {ticket_content}"
            )
        ).format(ticket_content=ticket_content)
        response = self.llm.invoke(prompt)
        clean_response = re.search(r'\{.*\}', response, re.DOTALL).group(0) if re.search(r'\{.*\}', response, re.DOTALL) else "{}"
        return json.loads(clean_response)

    def generate_improvements(self, ticket_content: str, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        suggestions = "\n".join(evaluation['suggestions'])
        prompt = "/think\n" + PromptTemplate(
            input_variables=["ticket_content", "suggestions"],
            template=(
                "Refine ticket: JSON {'title', 'description', 'requirements': list, 'acceptance_criteria': list}. Stick to original; improve clarity only. Only JSON.\n\n"
                "Ticket: {ticket_content}\nSuggestions: {suggestions}"
            )
        ).format(ticket_content=ticket_content, suggestions=suggestions)
        response = self.llm.invoke(prompt)
        clean_response = re.search(r'\{.*\}', response, re.DOTALL).group(0) if re.search(r'\{.*\}', response, re.DOTALL) else "{}"
        return json.loads(clean_response)

    def reflect_and_fix(self, refined_ticket: Dict[str, Any], original_content: str) -> Dict[str, Any]:
        refined_str = json.dumps(refined_ticket)
        prompt = (
            "/think\n"
            "Verify refined ticket against original: Ensure no added info/hallucinations, only clarifications.\n"
            "Original: {original_content}\n"
            "Fix if needed. Output only fixed JSON."
        ).format(original_content=original_content)
        response = self.llm.invoke(prompt + f"\nRefined: {refined_str}")
        clean_response = re.search(r'\{.*\}', response, re.DOTALL).group(0) if re.search(r'\{.*\}', response, re.DOTALL) else "{}"
        return json.loads(clean_response)

    def process(self, state: State) -> State:
        ticket_content = state['ticket_content']
        refined_ticket = ticket_content
        for _ in range(self.max_iterations):
            if isinstance(refined_ticket, dict):
                ticket_str = json.dumps(refined_ticket)
            else:
                ticket_str = refined_ticket
            evaluation = self.evaluate_clarity(ticket_str)
            refined_ticket = self.generate_improvements(ticket_str, evaluation)
            refined_ticket = self.reflect_and_fix(refined_ticket, ticket_content)  # Added reflection
        state['refined_ticket'] = refined_ticket

        # Post final ticket
        refined_ticket = state['refined_ticket']
        issue_url = state['url']
        repo_name = "/".join(issue_url.split('/')[3:5])
        issue_number = int(issue_url.split('/')[-1])
        repo = self.github.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        today = datetime.date.today().strftime("%Y%m%d")
        comment = f"Refined Ticket - {today}\n# {refined_ticket['title']}\n## Desc\n{refined_ticket['description']}\n## Req\n" + "\n".join(f"- {req}" for req in refined_ticket['requirements']) + "\n## AC\n" + "\n".join(f"- {ac}" for ac in refined_ticket['acceptance_criteria'])
        issue.create_comment(comment)
        return state
