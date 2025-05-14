import logging
from .state import State
from .config import LOGGER_LEVEL

class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(LOGGER_LEVEL)

    def __call__(self, state: State) -> State:
        self.logger.info(f"Starting agent: {self.name}")
        try:
            state = self.process(state)
            self.logger.info(f"Agent {self.name} completed successfully")
            return state
        except Exception as e:
            self.logger.error(f"Error in agent {self.name}: {str(e)}")
            raise

    def process(self, state: State) -> State:
        raise NotImplementedError("Subclasses must implement this method")
