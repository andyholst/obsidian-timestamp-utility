import json
import logging

from .base_agent import BaseAgent
from .state import State
from .utils import log_info

class OutputResultAgent(BaseAgent):
    def __init__(self):
        super().__init__("OutputResult")
        self.logger.setLevel(logging.INFO)
        log_info(self.logger, "Initialized OutputResultAgent")

    def process(self, state: State) -> State:
        """Log and return the final result from the state."""
        log_info(self.logger, f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        log_info(self.logger, "Starting output result process")
        result = state['result']
        log_info(self.logger, f"Final result content: {json.dumps(result, indent=2)}")
        log_info(self.logger, "Output result process completed")
        log_info(self.logger, f"After processing in {self.name}: {json.dumps(state, indent=2)}")
        return state
