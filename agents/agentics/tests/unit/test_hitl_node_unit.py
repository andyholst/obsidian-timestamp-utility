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

    @patch('builtins.input')
    @patch('builtins.print')
    def test_hitl_node_review_needed_low_score(self, mock_print, mock_input, monkeypatch):
        """Test HITL node when validation score is low (review needed)."""
        # Mock skip conditions to enable HITL execution
        monkeypatch.delenv('CI', raising=False)
        monkeypatch.setattr(sys, 'argv', ['test'])
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
        monkeypatch.setenv('HITL_ENABLED', 'true')
        mock_input.return_value = "User feedback: please improve error handling"
        node = HITLNode()
        original_state = {"validation_score": 75, "other_data": "test"}
        state = original_state.copy()

        result = node(state)

        # Print should be called
        mock_print.assert_called_once()
        assert "HITL Review Needed!" in str(mock_print.call_args)

        # Input should be called
        mock_input.assert_called_once()

        # Ensure immutability: original state unchanged
        assert state == original_state
        assert "human_feedback" not in state

        # Result is a new state dict with human_feedback added
        assert result != state
        assert result["human_feedback"] == "User feedback: please improve error handling"
        assert result["validation_score"] == 75
        assert result["other_data"] == "test"

    @patch('builtins.input')
    @patch('builtins.print')
    def test_hitl_node_review_needed_zero_score(self, mock_print, mock_input, monkeypatch):
        """Test HITL node when validation score is zero."""
        # Mock skip conditions to enable HITL execution
        monkeypatch.delenv('CI', raising=False)
        monkeypatch.setattr(sys, 'argv', ['test'])
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
        monkeypatch.setenv('HITL_ENABLED', 'true')
        mock_input.return_value = "Complete rewrite needed"
        node = HITLNode()
        state = {"validation_score": 0}

        result = node(state)

        mock_print.assert_called_once()
        mock_input.assert_called_once()
        assert result["human_feedback"] == "Complete rewrite needed"

    def test_hitl_node_no_validation_score(self, monkeypatch):
        """Test HITL node when no validation_score is present (defaults to 0)."""
        # Mock skip conditions to enable HITL execution
        monkeypatch.delenv('CI', raising=False)
        monkeypatch.setattr(sys, 'argv', ['test'])
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
        monkeypatch.setenv('HITL_ENABLED', 'true')
        node = HITLNode()
        state = {"other_data": "test"}

        with patch('builtins.input') as mock_input, \
             patch('builtins.print') as mock_print:
            mock_input.return_value = "Default feedback"

            result = node(state)

            mock_print.assert_called_once()
            mock_input.assert_called_once()
            assert result["human_feedback"] == "Default feedback"

    @patch('builtins.input')
    @patch('builtins.print')
    def test_hitl_node_preserves_state_data(self, mock_print, mock_input, monkeypatch):
        """Test that HITL node preserves all existing state data."""
        # Mock skip conditions to enable HITL execution
        monkeypatch.delenv('CI', raising=False)
        monkeypatch.setattr(sys, 'argv', ['test'])
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
        monkeypatch.setenv('HITL_ENABLED', 'true')
        mock_input.return_value = "Feedback"
        node = HITLNode()
        state = {
            "validation_score": 70,
            "generated_code": "some code",
            "generated_tests": "some tests",
            "refined_ticket": {"title": "Test"},
            "complex_nested_data": {"key": "value"}
        }

        result = node(state)

        # All original data should be preserved
        assert result["validation_score"] == 70
        assert result["generated_code"] == "some code"
        assert result["generated_tests"] == "some tests"
        assert result["refined_ticket"] == {"title": "Test"}
        assert result["complex_nested_data"] == {"key": "value"}
        assert result["human_feedback"] == "Feedback"