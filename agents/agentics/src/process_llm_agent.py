import json
import logging
import os

from .base_agent import BaseAgent
from .state import State
from .utils import remove_thinking_tags, log_info

class ProcessLLMAgent(BaseAgent):
    def __init__(self, llm_client, prompt_template):
        super().__init__("ProcessLLM")
        self.llm = llm_client
        self.prompt_template = prompt_template
        self.max_retries = int(os.getenv('LLM_MAX_RETRIES', 3))
        self.logger.setLevel(logging.INFO)
        log_info(self.logger, f"Initialized with max retries: {self.max_retries}")

    def process(self, state: State) -> State:
        """
        Process ticket content with LLM to extract structured task details and update the state.
        """
        log_info(self.logger, f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        log_info(self.logger, "Starting LLM processing")
        ticket_content = state.get('refined_ticket', state.get('ticket_content', ''))
        log_info(self.logger, f"Ticket content source: {'refined_ticket' if 'refined_ticket' in state else 'ticket_content'}")
        # If ticket_content is a dict, convert to string for the prompt
        if isinstance(ticket_content, dict):
            ticket_content = json.dumps(ticket_content)
        log_info(self.logger, f"Ticket content length: {len(ticket_content)}")
        log_info(self.logger, f"Ticket content: {ticket_content}")
        
        log_info(self.logger, "Formatting prompt with ticket content")
        prompt = self.prompt_template.format(ticket_content=ticket_content)
        log_info(self.logger, f"Prompt length: {len(prompt)}")
        log_info(self.logger, f"Prompt: {prompt}")
        
        for attempt in range(self.max_retries):
            log_info(self.logger, f"Attempt {attempt + 1} of {self.max_retries} to invoke LLM")
            response = self.llm.invoke(prompt)
            clean_response = remove_thinking_tags(response)
            log_info(self.logger, f"Cleaned LLM response length: {len(clean_response)}")
            log_info(self.logger, f"Cleaned LLM response: {clean_response}")
            try:
                result = json.loads(clean_response.strip())
                required_keys = {'title', 'description', 'requirements', 'acceptance_criteria'}
                if not required_keys.issubset(result.keys()):
                    raise ValueError("Missing required fields")
                if not isinstance(result['requirements'], list) or not isinstance(result['acceptance_criteria'], list):
                    raise ValueError("Requirements and acceptance criteria must be lists")
                state['result'] = result
                log_info(self.logger, f"Valid result parsed: {json.dumps(result, indent=2)}")
                log_info(self.logger, "LLM processing completed successfully")
                log_info(self.logger, f"After processing in {self.name}: {json.dumps(state, indent=2)}")
                return state
            except (ValueError, json.JSONDecodeError) as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Response length: {len(clean_response)}")
                self.logger.warning(f"Failed response: {clean_response}")
                if attempt == self.max_retries - 1:
                    self.logger.error(f"Invalid LLM response after {self.max_retries} attempts: {str(e)}")
                    raise ValueError(f"Invalid LLM response after {self.max_retries} attempts: {str(e)}")
        return state
