"""Human-in-the-Loop (HITL) node for conditional human review."""

class HITLNode:
    """Conditional human review node"""

    def __call__(self, state):
        score = state.get("validation_score", 0)
        if score < 80:  # Threshold from LLM_CODE_VALIDATION.md
            print("HITL Review Needed! State:", state)
            feedback = input("Enter feedback: ")  # Console-based pause for local use
            state["human_feedback"] = feedback
        return state