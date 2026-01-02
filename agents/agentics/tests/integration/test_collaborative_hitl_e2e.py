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
        assert len(result.validation_history) == 3
        assert result.validation_results is not None
        assert not result.validation_results.success
        assert result.feedback.get('max_iterations_exceeded') is True

    def test_hitl_node(self, dummy_llm, dummy_state, monkeypatch):
        """Test HITLNode with monkeypatched input captures human_feedback."""
        coll_gen = CollaborativeGenerator(dummy_llm, dummy_llm)
        result = coll_gen.generate_collaboratively(dummy_state)
        result_dict = asdict(result)

        def mock_readline():
            return "mock feedback\n"

        monkeypatch.setattr("sys.stdin.readline", mock_readline)

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