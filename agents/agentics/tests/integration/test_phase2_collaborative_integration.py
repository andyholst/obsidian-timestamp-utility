import pytest

from src.collaborative_generator import CollaborativeGenerator
from src.state import CodeGenerationState

from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage


@pytest.mark.integration
class TestPhase2CollaborativeIntegration:

    @pytest.fixture
    def dummy_llm_success(self):
        def _invoke(prompt: str) -> AIMessage:
            prompt_lower = prompt.lower()
            if "you are an expert software engineer validating" in prompt_lower:
                # Validation prompt - success
                content = '{"passed": true, "score": 95, "issues": [], "coverage_percentage": 100, "alignment_score": 100, "test_quality": "excellent"}'
                return AIMessage(content=content)
            elif "collaborative generation requirements" in prompt_lower or "code and tests collaboratively" in prompt_lower:
                collab_content = """// CODE ADDITIONS FOR main.ts
public testFunc(): string {
  console.log('Collaborative success');
  return 'success';
}
this.addCommand({
  id: 'collaborative-cmd',
  name: 'Collaborative Command',
  callback: () => {
    console.log('Command executed');
  }
});""" +
                """
// TEST ADDITIONS FOR main.test.ts
describe('testFunc', () => {
  it('covers generated code', () => {
    const result = plugin.testFunc();
    expect(result).toBe('success');
  });
});
describe('collaborative-cmd', () => {
  it('command registered', async () => {
    await plugin.onload();
    const command = mockCommands['collaborative-cmd'];
    expect(command).toBeDefined();
  });
});"""
                return AIMessage(content=collab_content)
            elif any(word in prompt_lower for word in ["test", "jest", "describe"]):
                # Test generation
                tests = """describe('testFunc', () => {
  it('covers generated code', () => {
    const result = plugin.testFunc();
    expect(result).toBe('success');
  });
});
describe('collaborative-cmd', () => {
  it('command registered', async () => {
    await plugin.onload();
    const command = mockCommands['collaborative-cmd'];
    expect(command).toBeDefined();
  });
});"""
                return AIMessage(content=tests, additional_kwargs={"tests": tests, "command_id": "test-collaborative"})
            else:
                # Code generation
                code = """public testFunc(): string {
  console.log('Collaborative success');
  return 'success';
}
this.addCommand({
  id: 'collaborative-cmd',
  name: 'Collaborative Command',
  callback: () => {
    console.log('Command executed');
  }
});"""
                return AIMessage(content=code, additional_kwargs={
                    "code": code,
                    "method_name": "testFunc",
                    "command_id": "collaborative-cmd"
                })
        return RunnableLambda(_invoke)

    @pytest.fixture
    def dummy_llm_fail_validation(self):
        def _invoke(prompt: str) -> AIMessage:
            prompt_lower = prompt.lower()
            if "you are an expert software engineer validating" in prompt_lower:
                # Validation prompt - failure
                content = '{"passed": false, "score": 40, "issues": ["Insufficient test coverage", "Method misalignment"]}'
                return AIMessage(content=content)
            elif any(word in prompt_lower for word in ["test", "jest", "describe"]):
                # Test generation - poor tests
                tests = """describe('Poor Tests', () => {
  it('fails', () => {
    expect(1).toBe(2);
  });
});"""
                return AIMessage(content=tests)
            else:
                # Code generation - problematic code
                code = """export function badFunc() {
  throw new Error('Intentional failure');
}"""
                return AIMessage(content=code, additional_kwargs={"code": code, "method_name": "badFunc"})
        return RunnableLambda(_invoke)

    def test_full_collaborative_flow_success(self, dummy_llm_success, dummy_state):
        """Test complete collaborative flow succeeds on first iteration."""
        coll_gen = CollaborativeGenerator(dummy_llm_success, dummy_llm_success)
        result = coll_gen.generate_collaboratively(dummy_state)

        assert result.generated_code is not None
        assert "testFunc" in result.generated_code
        assert result.generated_tests is not None
        assert "describe" in result.generated_tests
        assert result.validation_results is not None
        assert result.validation_results.success is True
        assert result.validation_results.score > 80
        assert len(result.validation_history) == 1  # Success on first iteration

    def test_collaborative_refinement_max_iterations(self, dummy_llm_fail_validation, dummy_state):
        """Test refinement loop runs all iterations when validation consistently fails."""
        coll_gen = CollaborativeGenerator(dummy_llm_fail_validation, dummy_llm_fail_validation)
        result = coll_gen.generate_collaboratively(dummy_state)

        assert result.generated_code is not None
        assert result.generated_tests is not None
        assert result.validation_results is not None
        assert result.validation_results.success is False
        assert result.validation_results.score == 60
        assert len(result.validation_history) == 3  # Max iterations reached
        assert result.feedback.get("max_iterations_exceeded") is True
        assert result.feedback.get("iteration_count") == 3

    def test_collaborative_state_immutability(self, dummy_llm_success, dummy_state):
        """Verify state immutability throughout collaborative process."""
        original_state = dummy_state
        coll_gen = CollaborativeGenerator(dummy_llm_success, dummy_llm_success)
        result = coll_gen.generate_collaboratively(original_state)

        # Original state unchanged
        assert original_state.generated_code is None
        assert original_state.validation_results is None

        # Result is new immutable state
        assert id(original_state) != id(result)
        assert result.issue_url == original_state.issue_url  # Preserved fields