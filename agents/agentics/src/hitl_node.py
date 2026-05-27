"""Human-in-the-Loop (HITL) node for conditional human review."""

import os
import sys


class HITLNode:
    """Conditional human review node"""

    def __call__(self, state):
        return self.invoke(state)

    def invoke(self, state):
        """Invoke HITL node - called by LangGraph."""
        # Get validation_score directly from state (not from validation_results)
        score = state.get("validation_score", 0)

        # If score is high enough, return state unchanged (no review needed)
        if score >= 80:
            return state

        # Check if HITL is disabled via environment
        if os.environ.get("CI"):
            return state

        if not os.environ.get("HITL_ENABLED"):
            return state

        # Check if running in non-interactive mode
        if not sys.stdout.isatty() and not os.environ.get("HITL_ENABLED"):
            return state

        # Low score - ask for human review
        try:
            print(f"HITL Review Needed!\nFull state dump:\n{state}")
            feedback = input("Human feedback (or Enter/EOF/Ctrl+C to proceed): ")
        except (EOFError, KeyboardInterrupt):
            feedback = "proceed"

        if not feedback.strip():
            feedback = "proceed"

        # Return new state with human_feedback
        result = state.copy()
        result["human_feedback"] = feedback
        return result
