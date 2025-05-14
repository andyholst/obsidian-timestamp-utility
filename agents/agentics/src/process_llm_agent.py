import json
import logging

from .base_agent import BaseAgent
from .state import State
from .utils import remove_thinking_tags

class ProcessLLMAgent(BaseAgent):
    def __init__(self, llm_client, prompt_template):
        super().__init__("ProcessLLM")
        self.llm = llm_client
        self.prompt_template = prompt_template
        self.logger.setLevel(logging.INFO)

    def process(self, state: State) -> State:
        self.logger.info(f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        self.logger.info("Starting LLM processing")
        ticket_content = state.get('refined_ticket', state['ticket_content'])
        self.logger.info(f"Ticket content source: {'refined_ticket' if 'refined_ticket' in state else 'ticket_content'}")
        # If ticket_content is a dict (e.g., from refinement), convert to string for the prompt
        if isinstance(ticket_content, dict):
            ticket_content = json.dumps(ticket_content)
        self.logger.info(f"Ticket content: {ticket_content}")
        
        self.logger.info("Formatting prompt with ticket content")
        prompt = self.prompt_template.format(ticket_content=ticket_content)
        self.logger.info(f"Prompt: {prompt}")
        
        max_retries = 3
        for attempt in range(max_retries):
            self.logger.info(f"Attempt {attempt + 1} of {max_retries} to invoke LLM")
            response = self.llm.invoke(prompt)
            clean_response = remove_thinking_tags(response)
            self.logger.info(f"LLM response: {clean_response}")
            try:
                result = json.loads(clean_response.strip())
                required_keys = {'title', 'description', 'requirements', 'acceptance_criteria'}
                if not required_keys.issubset(result.keys()):
                    raise ValueError("Missing required fields")
                if not isinstance(result['requirements'], list) or not isinstance(result['acceptance_criteria'], list):
                    raise ValueError("Requirements and acceptance criteria must be lists")
                state['result'] = result
                self.logger.info(f"Valid result parsed: {json.dumps(result, indent=2)}")
                self.logger.info("LLM processing completed successfully")
                self.logger.info(f"After processing in {self.name}: {json.dumps(state, indent=2)}")
                return state
            except (ValueError, json.JSONDecodeError) as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    self.logger.error(f"Invalid LLM response after {max_retries} attempts: {str(e)}")
                    raise ValueError(f"Invalid LLM response after {max_retries} attempts: {str(e)}")
        return state
