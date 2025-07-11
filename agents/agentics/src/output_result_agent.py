# output_result_agent.py
import json
import logging
from .base_agent import BaseAgent
from .state import State
from .utils import log_info

class OutputResultAgent(BaseAgent):
    def process(self, state: State) -> State:
        result = state['result']
        log_info(self.logger, f"Final result: {json.dumps(result, indent=2)}")
        return state
