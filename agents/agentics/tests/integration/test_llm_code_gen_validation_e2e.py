import pytest
from dataclasses import asdict

from src.code_generator_agent import CodeGeneratorAgent
from src.llm_validator import LLMResponseValidator
from src.code_validator import LLMCodeValidationPipeline
from src.models import CodeSpec, TestSpec
from src.state import CodeGenerationState

from langchain_core.messages import AIMessage


@pytest.mark.integration
class TestLLMCodeGenValidationE2E:
    """E2E integration tests for CodeGeneratorAgent.process, validators, and refine logic."""

    @pytest.fixture
    def result_dict(self):
        """Mock result dict for state."""
        return {
            "title": "Test",
            "description": "Test desc",
            "requirements": ["req1"],
            "acceptance_criteria": ["crit1"],
            "implementation_steps": [],
            "npm_packages": [],
        }

    @pytest.fixture
    def state_with_result(self, dummy_state, result_dict):
        """CodeGenerationState with populated result using dummy_state base."""
        code_spec = CodeSpec(language="typescript")
        test_spec = TestSpec(test_framework="jest")
        return CodeGenerationState(
            issue_url="",
            ticket_content="",
            title=result_dict["title"],
            description=result_dict["description"],
            requirements=result_dict["requirements"],
            acceptance_criteria=result_dict["acceptance_criteria"],
            code_spec=code_spec,
            test_spec=test_spec,
            result=result_dict,
        )

    @pytest.mark.parametrize(
        "mock_code, expected_method",
        [
            (
                """public testMethod() {
    console.log('test');
}
this.addCommand({
    id: 'test-command-id',
    name: 'Test Command'
});""",
                "testMethod",
            ),
            (
                """export function testMethod() {
    return true;
}""",
                "testMethod",
            ),
        ],
        ids=["class-method", "function-export"],
    )
    def test_agent_process_generates_valid_code(
        self, dummy_llm, state_with_result, temp_project_dir, monkeypatch, mock_code, expected_method
    ):
        """Test CodeGeneratorAgent.process generates code with validators passing."""
        state_dict = asdict(state_with_result)

        good_ts_code = mock_code
        good_jest_tests = """describe('Test Suite', () => {
    it('testMethod works', () => {
        expect(true).toBe(true);
    });
});"""

        def mock_llm_invoke(prompt, config=None):
            if "TypeScript code" in prompt:
                return AIMessage(content=good_ts_code)
            elif "Jest tests" in prompt:
                return AIMessage(content=good_jest_tests)
            return AIMessage(content="")

        monkeypatch.setattr(dummy_llm, "invoke", mock_llm_invoke)

        agent = CodeGeneratorAgent(dummy_llm)
        # Mock TS validation to pass (avoid real tsc/npx)
        monkeypatch.setattr(agent, "_validate_typescript_code", lambda self, code: True)
        # Mock deps lookup to avoid tool execution failures in isolated test environment
        monkeypatch.setattr(agent, "_get_available_dependencies", lambda self: [])

        state = agent.process(state_dict)

        assert "generated_code" in state
        assert len(state["generated_code"]) > 0
        assert expected_method in state["generated_code"]

        llm_val = LLMResponseValidator().validate_response(state["generated_code"], "code")
        assert llm_val["is_valid"]

        code_val = LLMCodeValidationPipeline().validate_typescript_code(
            state["generated_code"], state.get("generated_tests", "")
        )
        assert code_val.overall_score > 50

    def test_agent_process_refine_correction_chain(
        self, dummy_llm, state_with_result, temp_project_dir, monkeypatch
    ):
        """Test refine logic: mock validation fail -> correction_chain.invoke -> re-validate success."""
        state_dict = asdict(state_with_result)

        good_ts_code = """public testMethod() {
    console.log('test');
}"""
        corrected_ts_code = """public testMethod() {
    console.log('corrected test');
}"""
        good_jest_tests = """describe('Test Suite', () => {
    it('works', () => {
        expect(true).toBe(true);
    });
});"""

        def mock_llm_invoke(prompt, config=None):
            if "TypeScript code" in prompt:
                return AIMessage(content=good_ts_code)
            elif "correcting TypeScript code" in prompt:
                return AIMessage(content=corrected_ts_code)
            elif "Jest tests" in prompt:
                return AIMessage(content=good_jest_tests)
            return AIMessage(content="")

        monkeypatch.setattr(dummy_llm, "invoke", mock_llm_invoke)

        agent = CodeGeneratorAgent(dummy_llm)

        # Track correction chain invoke
        correction_called = False
        original_correction_invoke = agent.code_correction_chain.invoke

        def mock_correction_invoke(inputs):
            nonlocal correction_called
            correction_called = True
            return corrected_ts_code

        object.__setattr__(agent.code_correction_chain, "invoke", mock_correction_invoke)

        # Mock _validate_typescript_code: False first (original), True second (corrected)
        validate_call_count = [0]

        def mock_validate_typescript(self, code):
            validate_call_count[0] += 1
            if validate_call_count[0] == 1:
                return False  # Original validation fails -> trigger correction
            return True  # Corrected validation passes

        monkeypatch.setattr(CodeGeneratorAgent, "_validate_typescript_code", mock_validate_typescript)

        state = agent.process(state_dict)

        assert correction_called is True
        assert validate_call_count[0] == 2  # Original + corrected
        assert "generated_code" in state
        assert len(state["generated_code"]) > 0
        assert "testMethod" in state["generated_code"]