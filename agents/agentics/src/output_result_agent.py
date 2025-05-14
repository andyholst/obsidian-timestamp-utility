import json
import logging

from .base_agent import BaseAgent
from .state import State

class OutputResultAgent(BaseAgent):
    def __init__(self):
        super().__init__("OutputResult")
        self.logger.setLevel(logging.INFO)

    def process(self, state: State) -> State:
        self.logger.info(f"Before processing in {self.name}: {json.dumps(state, indent=2)}")
        self.logger.info("Starting output result process")
        result = state['result']
        self.logger.info(f"Final result: {json.dumps(result, indent=2)}")
        self.logger.info("Output result process completed")
        self.logger.info(f"After processing in {self.name}: {json.dumps(state, indent=2)}")
        return state
