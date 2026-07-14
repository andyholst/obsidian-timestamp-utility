import json
import logging

from .base_agent import BaseAgent
from .state import State
from .post_test_runner_agent import MAX_SELF_CORRECT_ATTEMPTS
from .utils import safe_json_dumps


class OutputResultAgent(BaseAgent):
    def __init__(self):
        super().__init__("OutputResult")
        self.monitor.logger.setLevel(logging.INFO)
        self.logger.debug("Initialized OutputResultAgent")

    def process(self, state: State) -> State:
        """Log and return the final result from the state.

        §5.4 Honest surfacing: when the bounded self-correct loop exhausted its attempts
        (recovery_attempt >= MAX_SELF_CORRECT_ATTEMPTS and the last gate still failed), set
        `self_correct_success=False` and `failing_gate` so the result is never reported as
        "done". The loop never claims success it did not earn.
        """
        self.logger.debug(
            f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}"
        )
        self.logger.debug("Starting output result process")
        result = state["result"]
        self.logger.debug(f"Final result content: {json.dumps(result, indent=2)}")
        self.logger.debug("Output result process completed")

        # §5.4 Honest reporting. The loop's recovery_attempt comes through on state.
        new_state = dict(state)
        recovery_attempt = state.get("recovery_attempt", 0) or 0
        # If the workflow escalated to hitl after exhausting attempts, the change did NOT
        # green its gate. Mark honestly.
        if int(recovery_attempt) >= MAX_SELF_CORRECT_ATTEMPTS:
            new_state["self_correct_success"] = False
            new_state["failing_gate"] = state.get("error_type") or "integration_testing"
            self.logger.warning(
                f"Self-correct loop exhausted {recovery_attempt} attempts; "
                f"self_correct_success=False, failing_gate={new_state['failing_gate']}"
            )
        else:
            new_state["self_correct_success"] = True
            new_state["failing_gate"] = ""

        self.logger.debug(
            f"After processing in {self.name}: {safe_json_dumps(new_state, indent=2)}"
        )
        return new_state
