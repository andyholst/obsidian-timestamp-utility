import pytest
import sys
from dataclasses import asdict

from src.collaborative_generator import CollaborativeGenerator
from src.hitl_node import HITLNode
from src.state_adapters import (
    StateToCodeGenerationStateAdapter,
    CodeGenerationStateToStateAdapter,
)
from src.state import CodeGenerationState

from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver


@pytest.mark.integration
class TestCollaborativeHITLE2E:
    """Integration tests for CollaborativeGenerator, HITLNode, state adapters, and checkpointer."""

    def test_collaborative_generator(self, dummy_llm, dummy_state):
        """Test CollaborativeGenerator.generate_collaboratively with refinement loops (dummy_llm causes validation failures)."""
        coll_gen = CollaborativeGenerator(dummy_llm, dummy_llm)
        result = coll_gen.generate_collaboratively(dummy_state)
        assert result.generated_code is not None
        assert result.generated_tests is not None
        assert result.validation_results is not None
        # dummy_llm produces output that may or may not pass validation depending on
        # cross_validate scoring. What matters is that the collaborative loop ran.
        assert len(result.validation_history) >= 1
        assert result.feedback.get("iteration_count", 0) >= 1

    def test_hitl_node_pass_through_when_not_opted_in(self, dummy_llm, dummy_state, monkeypatch):
        """HITLNode MUST be a no-op pass-through in automated/loop/CI runs.

        Per the hitl-optin spec: without both HITL_ENABLED=1 AND INTERACTIVE_HITL=1
        (or without a real TTY), the node returns state unchanged and MUST NOT add a
        `human_feedback` key. This is the behaviour the loop relies on, so the automated
        test asserts it directly (no flaky dependence on a TTY or model output).
        """
        coll_gen = CollaborativeGenerator(dummy_llm, dummy_llm)
        result = coll_gen.generate_collaboratively(dummy_state)
        result_dict = asdict(result)
        result_dict["validation_score"] = 50  # below threshold
        # Deliberately do NOT set HITL_ENABLED / INTERACTIVE_HITL — loop-excluded.
        monkeypatch.delenv("HITL_ENABLED", raising=False)
        monkeypatch.delenv("INTERACTIVE_HITL", raising=False)
        # Ensure no TTY even if the container happens to have one.
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        hitl = HITLNode()
        hitl_state = hitl(result_dict)
        # Pass-through: state unchanged, NO human_feedback key.
        assert "human_feedback" not in hitl_state
        assert hitl_state["validation_score"] == 50

    def test_hitl_node_opt_in_adds_feedback(self, dummy_llm, dummy_state, monkeypatch):
        """Opt-in interactive path: both flags + TTY + low score -> human_feedback added."""
        coll_gen = CollaborativeGenerator(dummy_llm, dummy_llm)
        result = coll_gen.generate_collaboratively(dummy_state)
        result_dict = asdict(result)
        result_dict["validation_score"] = 50  # below threshold
        monkeypatch.setenv("HITL_ENABLED", "1")
        monkeypatch.setenv("INTERACTIVE_HITL", "1")
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)  # pretend a real TTY

        def mock_input(prompt=""):
            return "mock feedback"

        monkeypatch.setattr("builtins.input", mock_input)

        hitl = HITLNode()
        hitl_state = hitl(result_dict)
        assert "human_feedback" in hitl_state
        assert hitl_state["human_feedback"] == "mock feedback"

    def test_state_adapters_roundtrip(self, dummy_state):
        """Test roundtrip through StateToCodeGenerationStateAdapter and back."""
        adapter_to = StateToCodeGenerationStateAdapter()
        adapter_from = CodeGenerationStateToStateAdapter()
        state_dict = asdict(dummy_state)
        adapted_to = adapter_to.invoke(state_dict)
        roundtrip_state = adapter_from.invoke(adapted_to)
        # Minimal state has generated_code=None
        assert roundtrip_state["generated_code"] == dummy_state.generated_code
        assert roundtrip_state["url"] == dummy_state.issue_url

    def test_checkpointer_memory_saver(self, dummy_llm, dummy_state):
        """Test minimal StateGraph with adapters and MemorySaver checkpointer."""
        coll_gen = CollaborativeGenerator(dummy_llm, dummy_llm)
        to_adapter = StateToCodeGenerationStateAdapter()
        from_adapter = CodeGenerationStateToStateAdapter()

        graph = StateGraph(dict)
        graph.add_node("to", to_adapter)
        graph.add_node("coll", coll_gen)
        graph.add_node("from", from_adapter)
        graph.add_edge("to", "coll")
        graph.add_edge("coll", "from")
        graph.set_entry_point("to")

        checkpointer = MemorySaver()
        app = graph.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "test"}}
        input_dict = asdict(dummy_state)
        output = app.invoke({"input": input_dict}, config)
        assert output is not None
