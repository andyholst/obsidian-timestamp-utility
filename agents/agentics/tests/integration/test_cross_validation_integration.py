import pytest

from src.collaborative_generator import CollaborativeGenerator
from src.state import CodeGenerationState

from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage


@pytest.mark.integration
class TestCrossValidationIntegration:

    @pytest.fixture
    def dummy_llm_validate_success(self):
        def _invoke(prompt: str) -> AIMessage:
            if "you are an expert software engineer validating" in prompt.lower():
                content = '{"passed": true, "score": 92, "issues": [], "coverage_percentage": 98, "alignment_score": 99, "test_quality": "excellent"}'
                return AIMessage(content=content)
            return AIMessage(content="")
        return RunnableLambda(_invoke)

    @pytest.fixture
    def dummy_llm_validate_fail(self):
        def _invoke(prompt: str) -> AIMessage:
            if "you are an expert software engineer validating" in prompt.lower():
                content = '{"passed": false, "score": 35, "issues": ["No test coverage for main method", "Missing edge case tests"], "coverage_percentage": 20, "alignment_score": 30, "test_quality": "poor"}'
                return AIMessage(content=content)
            return AIMessage(content="")
        return RunnableLambda(_invoke)

    @pytest.mark.parametrize(
        "llm_fixture, expected_success, expected_score, expected_issues_count",
        [
            ("dummy_llm_validate_success", True, 92, 0),
            ("dummy_llm_validate_fail", False, 35, 2),
        ],
        indirect=["llm_fixture"]
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

        coll_gen = CollaborativeGenerator(dummy_llm)
        validated_state = coll_gen.cross_validate(input_state)

        # Assertions
        assert validated_state.validation_results.success == expected_success
        assert validated_state.validation_results.score == expected_score
        assert len(validated_state.validation_results.errors) == expected_issues_count
        assert len(validated_state.validation_history) == 1
        assert id(input_state) != id(validated_state)  # State immutability

    def test_cross_validate_missing_fields(self, dummy_llm_validate_success, dummy_state):
        """Test cross_validate with state missing code or tests."""
        coll_gen = CollaborativeGenerator(dummy_llm_validate_success)
        validated = coll_gen.cross_validate(dummy_state)  # No code/tests

        assert validated.validation_results.success is False
        assert validated.validation_results.score < 50
        assert "code" in " ".join(validated.validation_results.errors).lower() or "test" in " ".join(validated.validation_results.errors).lower()