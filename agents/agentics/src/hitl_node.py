"""Human-in-the-Loop (HITL) node for conditional human review."""

import os
import sys

class HITLNode:
    """Conditional human review node"""

    def __call__(self, state):
        # Skip HITL in test environments or non-interactive mode
        if os.environ.get('CI') or 'pytest' in sys.argv[0] or not sys.stdout.isatty():
            return state

        score = state.get("validation_score", 0)
        if score < 80:
            if os.environ.get('HITL_ENABLED') == 'true':
                print("HITL Review Needed! State:", state)
                feedback = input("Enter feedback: ")
                state["human_feedback"] = feedback
            else:
                state["human_feedback"] = "Automated: proceeding without review"
        return state