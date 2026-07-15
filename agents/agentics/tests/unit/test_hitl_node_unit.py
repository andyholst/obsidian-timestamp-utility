import sys
import pytest
from unittest.mock import patch, MagicMock
from src.hitl_node import HITLNode


class TestHITLNode:
    """Test HITL node functionality."""

    def test_hitl_node_no_review_needed_high_score(self):
        """Test HITL node when validation score is high (no review needed)."""
        node = HITLNode()
        state = {"validation_score": 85, "other_data": "test"}

        result = node(state)

        # State should be unchanged
        assert result == state
        assert "human_feedback" not in result

    def test_hitl_node_no_review_needed_exact_threshold(self):
        """Test HITL node when validation score equals threshold (no review needed)."""
        node = HITLNode()
        state = {"validation_score": 80, "other_data": "test"}

        result = node(state)

        # State should be unchanged
        assert result == state
        assert "human_feedback" not in result

    def test_hitl_node_review_needed_low_score(
        self, monkeypatch
    ):
        """HITL is OPT-IN + loop-excluded: without INTERACTIVE_HITL=1 the node is a
        no-op pass-through even when HITL_ENABLED is set and stdin is a TTY (B21)."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setenv("HITL_ENABLED", "true")
        # INTERACTIVE_HITL intentionally NOT set -> pass-through
        node = HITLNode()
        original_state = {"validation_score": 75, "other_data": "test"}
        state = original_state.copy()

        result = node(state)

        # Pass-through: state unchanged, no human_feedback key added (B21)
        assert result == state
        assert "human_feedback" not in result
        assert "human_feedback" not in state

    def test_hitl_node_review_needed_zero_score(
        self, monkeypatch
    ):
        """Zero validation score still yields a no-op pass-through unless ALL HITL
        gates (incl INTERACTIVE_HITL) are set (B21)."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setenv("HITL_ENABLED", "true")
        node = HITLNode()
        state = {"validation_score": 0}

        result = node(state)

        # Pass-through: no human_feedback, state returned unchanged (B21)
        assert result == state
        assert "human_feedback" not in result

    def test_hitl_node_no_validation_score(self, monkeypatch):
        """HITL node with no validation_score defaults to a no-op pass-through
        in automated/loop runs (B21)."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setenv("HITL_ENABLED", "true")
        node = HITLNode()
        state = {"other_data": "test"}

        result = node(state)

        # Pass-through: state unchanged, no human_feedback key (B21)
        assert result == state
        assert "human_feedback" not in result

    def test_hitl_node_preserves_state_data(self, monkeypatch):
        """HITL node is a no-op pass-through in automated runs, so all existing
        state data is preserved and no human_feedback key is added (B21)."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setenv("HITL_ENABLED", "true")
        node = HITLNode()
        state = {
            "validation_score": 70,
            "generated_code": "some code",
            "generated_tests": "some tests",
            "refined_ticket": {"title": "Test"},
            "complex_nested_data": {"key": "value"},
        }

        result = node(state)

        # All original data preserved, no human_feedback added (pass-through, B21)
        assert result == state
        assert "human_feedback" not in result
        assert result["validation_score"] == 70
        assert result["generated_code"] == "some code"
        assert result["generated_tests"] == "some tests"
        assert result["refined_ticket"] == {"title": "Test"}
        assert result["complex_nested_data"] == {"key": "value"}
