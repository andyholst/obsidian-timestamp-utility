import json
import datetime
import re
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base_agent import BaseAgent
from .state import State
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from github import Github, GithubException
from .utils import safe_json_dumps, remove_thinking_tags, log_info, parse_json_response

class TicketClarityAgent(BaseAgent):
    def __init__(self, llm_client, github_client):
        super().__init__("TicketClarityAgent")
        self.llm = llm_client
        self.github = github_client
        self.max_iterations = 5
        self.monitor.setLevel(logging.INFO)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
    def process(self, state: State) -> State:
        log_info(self.name, f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        log_info(self.name, "Starting ticket clarity process")
        ticket_content = state['ticket_content']
        log_info(self.name, f"Initial ticket content: {ticket_content}")
        refined_ticket = self.refine_ticket(ticket_content)
        state['refined_ticket'] = refined_ticket
        log_info(self.name, f"Refined ticket: {json.dumps(refined_ticket, indent=2)}")
        self.post_final_ticket(state)
        log_info(self.name, "Ticket clarity process completed")
        log_info(self.name, f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        return state

    def refine_ticket(self, ticket_content):
        log_info(self.name, f"Refining ticket content: {json.dumps(ticket_content, indent=2)}")
        log_info(self.name, "Starting ticket refinement")
        refined_ticket = ticket_content
        for iteration in range(self.max_iterations):
            log_info(self.name, f"Refinement iteration {iteration + 1} of {self.max_iterations}")
            # Convert refined_ticket to string if it's a dictionary
            if isinstance(refined_ticket, dict):
                ticket_str = json.dumps(refined_ticket)
            else:
                ticket_str = refined_ticket
            log_info(self.name, f"Ticket string length for evaluation: {len(ticket_str)}")
            log_info(self.name, f"Ticket string for evaluation: {ticket_str}")
            
            evaluation = self.evaluate_clarity(ticket_str)
            log_info(self.name, f"Clarity evaluation: {evaluation}")
            # Validate evaluation response
            if not isinstance(evaluation, dict) or 'is_clear' not in evaluation or 'suggestions' not in evaluation:
                self.monitor.error(f"Invalid evaluation response: {evaluation}")
                raise ValueError("Invalid evaluation response")
            if evaluation['is_clear'] and iteration < self.max_iterations - 1:
                log_info(self.name, "Ticket is clear; continuing to next iteration")
                continue
            refined_ticket = self.generate_improvements(ticket_str, evaluation)
            log_info(self.name, f"Refined ticket after improvements: {json.dumps(refined_ticket, indent=2)}")
            # Validate refined ticket response
            if not isinstance(refined_ticket, dict) or not all(key in refined_ticket for key in ['title', 'description', 'requirements', 'acceptance_criteria']):
                self.monitor.error(f"Invalid refined ticket response: {refined_ticket}")
                raise ValueError("Invalid refined ticket response")
        log_info(self.name, "Ticket refinement completed")
        # Ensure refined_ticket is in the correct format
        if not isinstance(refined_ticket, dict):
            refined_ticket = {
                'title': 'Refined Ticket',
                'description': refined_ticket,
                'requirements': [],
                'acceptance_criteria': []
            }
        log_info(self.name, f"Refined ticket result: {json.dumps(refined_ticket, indent=2)}")
        return refined_ticket

    def evaluate_clarity(self, ticket_content):
        log_info(self.name, "Evaluating ticket clarity")
        prompt = "/think\n" + PromptTemplate(
            input_variables=["ticket_content"],
            template=(
                "Evaluate the clarity of the following ticket and provide a JSON object with 'is_clear' (boolean) and 'suggestions' (list of strings). "
                "Return only the JSON object without any additional text, code blocks, or explanations.\n\n"
                "Ticket:\n{ticket_content}\n\n"
                "JSON response:"
            )
        ).format(ticket_content=ticket_content)
        log_info(self.name, f"Clarity evaluation prompt: {prompt}")
        
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        log_info(self.name, f"LLM response for evaluate_clarity: {clean_response}")
        result = parse_json_response(clean_response)
        log_info(self.name, f"Parsed evaluation: {result}")
        return result

    def generate_improvements(self, ticket_content, evaluation):
        log_info(self.name, "Generating ticket improvements")
        suggestions = evaluation['suggestions']
        log_info(self.name, f"Suggestions for improvement: {suggestions}")
        prompt = "/think\n" + PromptTemplate(
            input_variables=["ticket_content", "suggestions"],
            template=(
                "Refine the following ticket based on these suggestions and return only a JSON object with 'title', 'description', 'requirements' (list), and 'acceptance_criteria' (list). "
                "Do not include any additional text, code blocks, or explanations.\n\n"
                "Ticket:\n{ticket_content}\n\n"
                "Suggestions:\n{suggestions}\n\n"
                "JSON response:"
            )
        ).format(ticket_content=ticket_content, suggestions="\n".join(suggestions))
        log_info(self.name, f"Improvements prompt: {prompt}")
        
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        log_info(self.name, f"LLM response for generate_improvements: {clean_response}")
        result = parse_json_response(clean_response)
        log_info(self.name, f"Parsed improvements: {result}")
        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
    def post_final_ticket(self, state):
        log_info(self.name, "Posting final refined ticket to GitHub")
        refined_ticket = state['refined_ticket']
        issue_url = state['url']
        log_info(self.name, f"Issue URL: {issue_url}")
        repo_name = "/".join(issue_url.split('/')[3:5])
        issue_number = int(issue_url.split('/')[-1])
        log_info(self.name, f"Repository: {repo_name}, Issue number: {issue_number}")

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
        log_info(self.name, f"Comment to post: {comment}")
        try:
            issue.create_comment(comment)
        except GithubException as e:
            self.monitor.error(f"Failed to create comment: {e}")
        log_info(self.name, "Refined ticket posted successfully")
