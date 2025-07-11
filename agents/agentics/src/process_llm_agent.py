# process_llm_agent.py
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
        self.max_retries = int(os.getenv('LLM_MAX_RETRIES', 2))
        self.max_reflect = 2  # Added reflection

    def reflect_and_fix(self, result_json: str, ticket_content: str) -> str:
        prompt = (
            "/think\n"
            "Verify JSON against ticket: Ensure fields match exactly, no extras/hallucinations.\n"
            "Ticket: {ticket_content}\n"
            "Fix if needed. Output only fixed JSON."
        ).format(ticket_content=ticket_content)
        response = self.llm.invoke(prompt + f"\nJSON: {result_json}")
        return remove_thinking_tags(response).strip()

    def process(self, state: State) -> State:
        ticket_content = state.get('refined_ticket', state.get('ticket_content', ''))
        if isinstance(ticket_content, dict):
            ticket_content = json.dumps(ticket_content)
        
        prompt = self.prompt_template.format(ticket_content=ticket_content)
        
        for attempt in range(self.max_retries):
            response = self.llm.invoke(prompt)
            clean_response = remove_thinking_tags(response)
            try:
                result = json.loads(clean_response.strip())
                if not all(key in result for key in ['title', 'description', 'requirements', 'acceptance_criteria']):
                    raise ValueError("Missing fields")
                if not isinstance(result['requirements'], list) or not isinstance(result['acceptance_criteria'], list):
                    raise ValueError("Invalid types")
                
                result_json = json.dumps(result)
                # Self-reflection loop
                for _ in range(self.max_reflect):
                    fixed = self.reflect_and_fix(result_json, ticket_content)
                    if fixed == result_json:
                        break
                    result_json = fixed
                state['result'] = json.loads(result_json)
                return state
            except (ValueError, json.JSONDecodeError) as e:
                if attempt == self.max_retries - 1:
                    raise ValueError(f"Invalid response after retries: {e}")
        return state
