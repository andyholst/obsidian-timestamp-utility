"""
Integration tests for cross-validation in the agentics workflow.
Tests the CollaborativeGenerator.cross_validate method.
"""

import pytest
from unittest.mock import MagicMock
from src.collaborative_generator import CollaborativeGenerator
from src.state import CodeGenerationState, CodeSpec, TestSpecification
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage


def _make_mock_llm():
    """Create a mock LLM that returns valid JSON responses."""
    return RunnableLambda(
        lambda p: AIMessage(
            content='{"valid": true, "score": 80, "issues": [], "feedback": "Looks good"}'
        )
    )


@pytest.mark.integration
class TestCrossValidationIntegration:
    """Integration tests for cross-validation."""

    @pytest.fixture
    def dummy_state(self):
        """Create a minimal CodeGenerationState for testing."""
        return CodeGenerationState(
            issue_url="",
            ticket_content="",
            title="",
            description="",
            requirements=[],
            acceptance_criteria=[],
            code_spec=CodeSpec(language=""),
            test_spec=TestSpecification(test_framework=""),
            history=[],
        )

    def test_cross_validate_success(self, dummy_state):
        """Test cross_validate with valid code and tests."""
        mock_llm = _make_mock_llm()
        coll_gen = CollaborativeGenerator(mock_llm, mock_llm)

        code = """export function validatedMethod() {
  return true;
}"""
        tests = """describe('Validated Tests', () => {
  it('tests validatedMethod', () => {
    expect(validatedMethod()).toBe(true);
  });
});"""

        input_state = dummy_state.with_code(code).with_tests(tests)
        validated_state = coll_gen.cross_validate(input_state)

        # Verify result structure
        assert validated_state is not None
        assert validated_state.validation_results is not None
        assert isinstance(validated_state.validation_results.success, bool)
        assert isinstance(validated_state.validation_results.score, (int, float))
        assert len(validated_state.validation_history) >= 1
        # State immutability
        assert id(input_state) != id(validated_state)

    def test_cross_validate_failure(self, dummy_state):
        """Test cross_validate with invalid code."""
        mock_llm = _make_mock_llm()
        coll_gen = CollaborativeGenerator(mock_llm, mock_llm)

        code = """export function invalidMethod() {
  throw new Error('fail');
}"""
        tests = """describe('Invalid Tests', () => {
  it('no coverage', () => {});
});"""

        input_state = dummy_state.with_code(code).with_tests(tests)
        validated_state = coll_gen.cross_validate(input_state)

        # Verify result structure
        assert validated_state is not None
        assert validated_state.validation_results is not None
        assert isinstance(validated_state.validation_results.success, bool)

    def test_cross_validate_missing_fields(self, dummy_state):
        """Test cross_validate with state missing code or tests."""
        # Use a mock LLM that detects missing code/tests
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(
            content='{"valid": false, "score": 20, "issues": ["No code generated", "No tests generated"]}'
        )

        coll_gen = CollaborativeGenerator(mock_llm, mock_llm)

        # No code/tests in dummy_state
        validated = coll_gen.cross_validate(dummy_state)

        # Should handle missing fields gracefully
        assert validated is not None
        assert validated.validation_results is not None
        # With no code/tests, validation should report issues
        assert len(validated.validation_results.errors) > 0

    def test_cross_validate_with_mock_validation(self, dummy_state):
        """Test cross_validate with controlled mock responses."""
        # Create a mock LLM that returns a specific validation result
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(
            content='{"valid": true, "score": 90, "issues": []}'
        )

        coll_gen = CollaborativeGenerator(mock_llm, mock_llm)

        code = "function test() { return true; }"
        tests = "test('test', () => { expect(true).toBe(true); });"

        input_state = dummy_state.with_code(code).with_tests(tests)
        validated_state = coll_gen.cross_validate(input_state)

        # Verify the validation was performed
        assert validated_state is not None
        assert validated_state.validation_results is not None
