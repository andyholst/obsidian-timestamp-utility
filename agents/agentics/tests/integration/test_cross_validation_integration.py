import pytest
import time
from unittest.mock import Mock, patch

from src.collaborative_generator import CollaborativeGenerator
from src.state import CodeGenerationState
from src.clients import llm_code, llm_reasoning


@pytest.mark.integration
class TestCrossValidationIntegration:

    @pytest.fixture
    def real_llm_validate_success(self):
        """Use real Ollama LLM for successful validation."""
        return llm_code

    @pytest.fixture
    def real_llm_validate_fail(self):
        """Use real Ollama LLM for validation failure scenarios."""
        return llm_code

    @pytest.mark.parametrize(
        "llm_fixture, expected_success, expected_score, expected_issues_count",
        [
            ("real_llm_validate_success", True, 80, 1),
            ("real_llm_validate_fail", False, 60, 2),
        ]
    )
    def test_cross_validate(
        self, request, dummy_state, llm_fixture, expected_success, expected_score, expected_issues_count
    ):
        """Parametrized test for cross_validate success/failure cases."""
        dummy_llm = request.getfixturevalue(llm_fixture)

        # Create input state with code and tests
        if "success" in llm_fixture:
            code = """export function validatedMethod() {
  return true;
}"""
            tests = """describe('Validated Tests', () => {
  it('tests validatedMethod', () => {
    expect(validatedMethod()).toBe(true);
  });
});"""
        else:
            code = """export function invalidMethod() {
  throw new Error('fail');
}"""
            tests = """describe('Invalid Tests', () => {
  it('no coverage', () => {});
});"""

        input_state = dummy_state.with_code(code).with_tests(tests)

        coll_gen = CollaborativeGenerator(llm_reasoning, dummy_llm)
        validated_state = coll_gen.cross_validate(input_state)

        # Assertions
        assert validated_state.validation_results.success == expected_success
        assert validated_state.validation_results.score == expected_score
        assert len(validated_state.validation_results.errors) == expected_issues_count
        assert len(validated_state.validation_history) == 1
        assert id(input_state) != id(validated_state)  # State immutability

    def test_cross_validate_missing_fields(self, real_llm_validate_success, dummy_state):
        """Test cross_validate with state missing code or tests."""
        coll_gen = CollaborativeGenerator(llm_reasoning, real_llm_validate_success)
        validated = coll_gen.cross_validate(dummy_state)  # No code/tests

        assert validated.validation_results.success is False
        assert validated.validation_results.score < 80
        assert "code" in " ".join(validated.validation_results.errors).lower() or "test" in " ".join(validated.validation_results.errors).lower()