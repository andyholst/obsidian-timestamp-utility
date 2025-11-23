import json
import logging

from .base_agent import BaseAgent
from .state import State
from .utils import safe_json_dumps

class OutputResultAgent(BaseAgent):
    def __init__(self):
        super().__init__("OutputResult")
        self.monitor.logger.setLevel(logging.INFO)
        self.logger.debug("Initialized OutputResultAgent")

    def process(self, state: State) -> State:
        """Log and return the final result from the state."""
        self.logger.debug(f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        self.logger.debug("Starting output result process")
        result = state['result']
        self.logger.debug(f"Final result content: {json.dumps(result, indent=2)}")
        self.logger.debug("Output result process completed")
        self.logger.debug(f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        return state
