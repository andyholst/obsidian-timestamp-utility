import json
import datetime
import re
from .base_agent import BaseAgent
from .state import State
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from github import Github

class TicketClarityAgent(BaseAgent):
    def __init__(self, llm_client, github_client):
        super().__init__("TicketClarityAgent")
        self.llm = llm_client
        self.github = github_client
        self.max_iterations = 5

    def process(self, state: State) -> State:
        ticket_content = state['ticket_content']
        refined_ticket = self.refine_ticket(ticket_content)
        state['refined_ticket'] = refined_ticket
        self.post_final_ticket(state)
        return state

    def refine_ticket(self, ticket_content):
        refined_ticket = ticket_content
        for iteration in range(self.max_iterations):
            # Convert refined_ticket to string if it's a dictionary
            if isinstance(refined_ticket, dict):
                ticket_str = json.dumps(refined_ticket)
            else:
                ticket_str = refined_ticket
            evaluation = self.evaluate_clarity(ticket_str)
            # Validate evaluation response
            if not isinstance(evaluation, dict) or 'is_clear' not in evaluation or 'suggestions' not in evaluation:
                self.logger.error("Invalid evaluation response: %s", evaluation)
                raise ValueError("Invalid evaluation response")
            if iteration < self.max_iterations - 1 and evaluation['is_clear']:
                continue  # Always perform all 5 iterations
            refined_ticket = self.generate_improvements(ticket_str, evaluation)
            # Validate refined ticket response
            if not isinstance(refined_ticket, dict) or not all(key in refined_ticket for key in ['title', 'description', 'requirements', 'acceptance_criteria']):
                self.logger.error("Invalid refined ticket response: %s", refined_ticket)
                raise ValueError("Invalid refined ticket response")
        return refined_ticket

    def evaluate_clarity(self, ticket_content):
        prompt = PromptTemplate(
            input_variables=["ticket_content"],
            template=(
                "Evaluate the clarity of the following ticket and provide a JSON object with 'is_clear' (boolean) and 'suggestions' (list of strings). "
                "Only return the JSON object, nothing else.\n\n"
                "Ticket:\n{ticket_content}\n\n"
                "JSON response:"
            )
        ).format(ticket_content=ticket_content)
        response = self.llm.invoke(prompt)
        self.logger.info(f"LLM response for evaluate_clarity: {response}")
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            self.logger.error(f"JSONDecodeError: {e}")
            # Attempt to extract JSON from the response
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError("LLM did not return a valid JSON object")

    def generate_improvements(self, ticket_content, evaluation):
        suggestions = evaluation['suggestions']
        prompt = PromptTemplate(
            input_variables=["ticket_content", "suggestions"],
            template=(
                "Refine the following ticket based on these suggestions and return only a JSON object with 'title', 'description', 'requirements' (list), and 'acceptance_criteria' (list). "
                "Do not include any additional text or explanations.\n\n"
                "Ticket:\n{ticket_content}\n\n"
                "Suggestions:\n{suggestions}\n\n"
                "JSON response:"
            )
        ).format(ticket_content=ticket_content, suggestions="\n".join(suggestions))
        response = self.llm.invoke(prompt)
        self.logger.info(f"LLM response for generate_improvements: {response}")
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            self.logger.error(f"JSONDecodeError: {e}")
            # Attempt to extract JSON from the response
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError("LLM did not return a valid JSON object")

    def post_final_ticket(self, state):
        refined_ticket = state['refined_ticket']
        issue_url = state['url']
        repo_name = "/".join(issue_url.split('/')[3:5])
        issue_number = int(issue_url.split('/')[-1])
        repo = self.github.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        today = datetime.date.today().strftime("%Y%m%d")
        comment = (
            f"TicketClarityAgent - Refined Ticket - {today}\n\n"
            f"# {refined_ticket['title']}\n\n"
            f"## Description\n{refined_ticket['description']}\n\n"
            f"## Requirements\n" + "\n".join(f"- {req}" for req in refined_ticket['requirements']) + "\n\n"
            f"## Acceptance Criteria\n" + "\n".join(f"- {ac}" for ac in refined_ticket['acceptance_criteria'])
        )
        issue.create_comment(comment)
