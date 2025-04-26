import logging
from .state import State

class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)

    def __call__(self, state: State) -> State:
        try:
            self.logger.info(f"Starting {self.name}")
            state = self.process(state)
            self.logger.info(f"Completed {self.name}")
            return state
        except Exception as e:
            self.logger.error(f"Error in {self.name}: {e}")
            raise

    def process(self, state: State) -> State:
        raise NotImplementedError("Subclasses must implement this method")
