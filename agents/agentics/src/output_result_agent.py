import json
from .base_agent import BaseAgent
from .state import State

class OutputResultAgent(BaseAgent):
    def __init__(self):
        super().__init__("OutputResult")

    def process(self, state: State) -> State:
        result = state['result']
        self.logger.info("Final result:\n" + json.dumps(result, indent=2))
        return state
