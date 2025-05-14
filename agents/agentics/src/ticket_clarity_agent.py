import json
import datetime
import re
import logging

from .base_agent import BaseAgent
from .state import State
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from github import Github
from .utils import remove_thinking_tags

class TicketClarityAgent(BaseAgent):
    def __init__(self, llm_client, github_client):
        super().__init__("TicketClarityAgent")
        self.llm = llm_client
        self.github = github_client
        self.max_iterations = 5
        self.logger.setLevel(logging.INFO)

    def process(self, state: State) -> State:
        self.logger.info(f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        self.logger.info("Starting ticket clarity process")
        ticket_content = state['ticket_content']
        self.logger.info(f"Initial ticket content: {ticket_content}")
        refined_ticket = self.refine_ticket(ticket_content)
        state['refined_ticket'] = refined_ticket
        self.logger.info(f"Refined ticket: {json.dumps(refined_ticket, indent=2)}")
        self.post_final_ticket(state)
        self.logger.info("Ticket clarity process completed")
        self.logger.info(f"After processing in {self.name}: {json.dumps(state, indent=2)}")
        return state

    def refine_ticket(self, ticket_content):
        self.logger.info(f"Refining ticket content: {json.dumps(ticket_content, indent=2)}")
        self.logger.info("Starting ticket refinement")
        refined_ticket = ticket_content
        for iteration in range(self.max_iterations):
            self.logger.info(f"Refinement iteration {iteration + 1} of {self.max_iterations}")
            # Convert refined_ticket to string if it's a dictionary
            if isinstance(refined_ticket, dict):
                ticket_str = json.dumps(refined_ticket)
            else:
                ticket_str = refined_ticket
            self.logger.info(f"Ticket string for evaluation: {ticket_str}")
            
            evaluation = self.evaluate_clarity(ticket_str)
            self.logger.info(f"Clarity evaluation: {evaluation}")
            # Validate evaluation response
            if not isinstance(evaluation, dict) or 'is_clear' not in evaluation or 'suggestions' not in evaluation:
                self.logger.error(f"Invalid evaluation response: {evaluation}")
                raise ValueError("Invalid evaluation response")
            if evaluation['is_clear'] and iteration < self.max_iterations - 1:
                self.logger.info("Ticket is clear; continuing to next iteration")
                continue
            refined_ticket = self.generate_improvements(ticket_str, evaluation)
            self.logger.info(f"Refined ticket after improvements: {json.dumps(refined_ticket, indent=2)}")
            # Validate refined ticket response
            if not isinstance(refined_ticket, dict) or not all(key in refined_ticket for key in ['title', 'description', 'requirements', 'acceptance_criteria']):
                self.logger.error(f"Invalid refined ticket response: {refined_ticket}")
                raise ValueError("Invalid refined ticket response")
        self.logger.info("Ticket refinement completed")
        self.logger.info(f"Refined ticket result: {json.dumps(refined_ticket, indent=2)}")
        return refined_ticket

    def evaluate_clarity(self, ticket_content):
        self.logger.info("Evaluating ticket clarity")
        prompt = "/think\n" + PromptTemplate(
            input_variables=["ticket_content"],
            template=(
                "Evaluate the clarity of the following ticket and provide a JSON object with 'is_clear' (boolean) and 'suggestions' (list of strings). "
                "Only return the JSON object, nothing else.\n\n"
                "Ticket:\n{ticket_content}\n\n"
                "JSON response:"
            )
        ).format(ticket_content=ticket_content)
        self.logger.info(f"Clarity evaluation prompt: {prompt}")
        
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        self.logger.info(f"LLM response for evaluate_clarity: {clean_response}")
        try:
            result = json.loads(clean_response.strip())
            self.logger.info(f"Parsed evaluation: {result}")
            return result
        except json.JSONDecodeError as e:
            self.logger.error(f"JSONDecodeError: {str(e)}")
            match = re.search(r'\{.*\}', clean_response, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(0))
                    self.logger.info(f"Recovered evaluation from regex: {result}")
                    return result
                except json.JSONDecodeError:
                    pass
            self.logger.error("LLM did not return a valid JSON object")
            raise ValueError("LLM did not return a valid JSON object")

    def generate_improvements(self, ticket_content, evaluation):
        self.logger.info("Generating ticket improvements")
        suggestions = evaluation['suggestions']
        self.logger.info(f"Suggestions for improvement: {suggestions}")
        prompt = "/think\n" + PromptTemplate(
            input_variables=["ticket_content", "suggestions"],
            template=(
                "Refine the following ticket based on these suggestions and return only a JSON object with 'title', 'description', 'requirements' (list), and 'acceptance_criteria' (list). "
                "Do not include any additional text or explanations.\n\n"
                "Ticket:\n{ticket_content}\n\n"
                "Suggestions:\n{suggestions}\n\n"
                "JSON response:"
            )
        ).format(ticket_content=ticket_content, suggestions="\n".join(suggestions))
        self.logger.info(f"Improvements prompt: {prompt}")
        
        response = self.llm.invoke(prompt)
        clean_response = remove_thinking_tags(response)
        self.logger.info(f"LLM response for generate_improvements: {clean_response}")
        try:
            result = json.loads(clean_response.strip())
            self.logger.info(f"Parsed improvements: {result}")
            return result
        except json.JSONDecodeError as e:
            self.logger.error(f"JSONDecodeError: {str(e)}")
            match = re.search(r'\{.*\}', clean_response, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(0))
                    self.logger.info(f"Recovered improvements from regex: {result}")
                    return result
                except json.JSONDecodeError:
                    pass
            self.logger.error("LLM did not return a valid JSON object")
            raise ValueError("LLM did not return a valid JSON object")

    def post_final_ticket(self, state):
        self.logger.info("Posting final refined ticket to GitHub")
        refined_ticket = state['refined_ticket']
        issue_url = state['url']
        self.logger.info(f"Issue URL: {issue_url}")
        repo_name = "/".join(issue_url.split('/')[3:5])
        issue_number = int(issue_url.split('/')[-1])
        self.logger.info(f"Repository: {repo_name}, Issue number: {issue_number}")
        try:
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
            self.logger.info(f"Comment to post: {comment}")
            issue.create_comment(comment)
            self.logger.info("Refined ticket posted successfully")
        except Exception as e:
            self.logger.error(f"Failed to post refined ticket: {str(e)}")
            raise
