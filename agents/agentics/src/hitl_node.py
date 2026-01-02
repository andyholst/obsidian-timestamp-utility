"""Human-in-the-Loop (HITL) node for conditional human review."""

import os
import sys

class HITLNode:
    """Conditional human review node"""

    def __call__(self, state):
        state_copy = state.copy()
        if os.environ.get('CI'):
            state_copy["human_feedback"] = "Skipped in CI"
            return state_copy

        elif bool(os.getenv('INTEGRATION_TEST')):
            state_copy["human_feedback"] = "auto-approved for integration test"
            return state_copy

        validation_results = state_copy.get("validation_results", {})
        score = validation_results.get("score", 0)
        if score < 80:
            print(f"HITL Review Needed (score={score}/100)!")
            print("Full state dump:")
            print(state_copy)
            try:
                feedback = input("Human feedback (or Enter/EOF/Ctrl+C to proceed): ")
            except (EOFError, KeyboardInterrupt):
                feedback = "proceed"
            if not feedback.strip():
                feedback = "proceed"
            state_copy["human_feedback"] = feedback
        return state_copy