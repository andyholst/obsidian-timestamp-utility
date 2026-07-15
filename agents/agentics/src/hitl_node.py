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

        # Never block automated/CI/loop runs. HITL only engages when it is
        # *explicitly* enabled AND the session is genuinely interactive (a real
        # TTY on stdin). Any leaked HITL_ENABLED from a prior test, or a piped
        # loop harness, must NOT trigger a blocking input() prompt.
        if os.environ.get("CI"):
            return state

        # HITL requires TWO explicit opt-ins so a leaked HITL_ENABLED (e.g. from a
        # killed test that never reverted its monkeypatch) can never trigger a
        # blocking input() prompt in an automated/loop/CI run. INTERACTIVE_HITL=1
        # is only set deliberately, never by tests that merely flip HITL_ENABLED.
        hitl_enabled = os.environ.get("HITL_ENABLED", "").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        interactive_hitl = os.environ.get("INTERACTIVE_HITL", "").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if not (hitl_enabled and interactive_hitl):
            return state

        if not sys.stdin.isatty():
            return state

        # Low score + explicitly enabled + interactive - ask for human review
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
