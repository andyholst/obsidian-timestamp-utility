import json
from .base_agent import BaseAgent
from .state import State

class ProcessLLMAgent(BaseAgent):
    def __init__(self, llm_client, prompt_template):
        super().__init__("ProcessLLM")
        self.llm = llm_client
        self.prompt_template = prompt_template

    def process(self, state: State) -> State:
        ticket_content = state.get('refined_ticket', state['ticket_content'])
        # If ticket_content is a dict (e.g., from refinement), convert to string for the prompt
        if isinstance(ticket_content, dict):
            ticket_content = json.dumps(ticket_content)
        prompt = self.prompt_template.format(ticket_content=ticket_content)
        max_retries = 3
        for attempt in range(max_retries):
            response = self.llm.invoke(prompt)
            try:
                result = json.loads(response.strip())
                required_keys = {'title', 'description', 'requirements', 'acceptance_criteria'}
                if not required_keys.issubset(result.keys()):
                    raise ValueError("Missing required fields")
                if not isinstance(result['requirements'], list) or not isinstance(result['acceptance_criteria'], list):
                    raise ValueError("Requirements and acceptance criteria must be lists")
                state['result'] = result
                return state
            except (ValueError) as e:
                if attempt == max_retries - 1:
                    raise ValueError(f"Invalid LLM response after {max_retries} attempts: {str(e)}")
                self.logger.warning(f"Retrying due to error: {e}")
