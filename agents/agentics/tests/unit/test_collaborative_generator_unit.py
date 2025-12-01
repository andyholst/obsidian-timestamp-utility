import pytest
import pytest_asyncio
import json
import os
from unittest.mock import patch, MagicMock, call
from src.collaborative_generator import CollaborativeGenerator
from src.state import CodeGenerationState
from src.models import CodeSpec, TestSpec, ValidationResults
from src.services import ServiceManager
from src.config import get_config


@pytest_asyncio.fixture
async def service_manager():
    """Create a service manager with mocked clients for testing."""
    config = get_config()
    sm = ServiceManager(config)

    # Mock the clients to simulate real behavior
    sm.ollama_reasoning = MagicMock()
    sm.ollama_reasoning.invoke.return_value = json.dumps({
        "passed": True,
        "score": 95,
        "coverage_percentage": 90,
        "alignment_score": 95,
        "issues": [],
        "recommendations": [],
        "test_quality": "excellent"
    })

    sm.ollama_code = MagicMock()
    sm.ollama_code.invoke.return_value = "generated code content"

    return sm


@pytest.fixture
def sample_code_generation_state():
    """Create a sample CodeGenerationState for testing."""
    return CodeGenerationState(
        issue_url="https://github.com/test/repo/issues/123",
        ticket_content="Add UUID generator command",
        title="Add UUID Generator",
        description="Add a command to generate UUIDs",
        requirements=["Generate UUID v7", "Insert at cursor"],
        acceptance_criteria=["UUID is valid", "Inserted correctly"],
        code_spec=CodeSpec(language="typescript", framework="obsidian"),
        test_spec=TestSpec(test_framework="jest"),
        generated_code="export function generateUUID() { return 'uuid'; }",
        generated_tests="describe('generateUUID', () => { it('works', () => {}); });"
    )


class TestCollaborativeGenerator:
    """Comprehensive unit tests for CollaborativeGenerator class."""

    def test_initialization(self, service_manager):
        """Test CollaborativeGenerator initialization."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        assert generator.name == "CollaborativeGenerator"
        assert generator.llm == service_manager.ollama_reasoning
        assert generator.llm_reasoning == service_manager.ollama_reasoning
        assert generator.llm_code == service_manager.ollama_reasoning
        assert generator.max_refinement_iterations == 3
        assert hasattr(generator, 'code_generator')
        assert hasattr(generator, 'test_generator')
        assert hasattr(generator, 'circuit_breaker')

    @patch('src.collaborative_generator.get_circuit_breaker')
    def test_circuit_breaker_initialization(self, mock_get_circuit_breaker, service_manager):
        """Test circuit breaker is properly initialized."""
        mock_circuit_breaker = MagicMock()
        mock_get_circuit_breaker.return_value = mock_circuit_breaker

        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        mock_get_circuit_breaker.assert_called_once_with("collaborative_generation")
        assert generator.circuit_breaker == mock_circuit_breaker

    def test_invoke_method(self, service_manager, sample_code_generation_state):
        """Test invoke method delegates to generate_collaboratively."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        with patch.object(generator, 'generate_collaboratively') as mock_generate:
            mock_generate.return_value = sample_code_generation_state

            result = generator.invoke(sample_code_generation_state)

            mock_generate.assert_called_once_with(sample_code_generation_state)
            assert result == sample_code_generation_state

    @patch('src.collaborative_generator.log_info')
    @patch.dict(os.environ, {'PROJECT_ROOT': '/tmp/test'})
    def test_generate_collaboratively_success_first_iteration(self, mock_log_info, service_manager, sample_code_generation_state):
        """Test successful collaborative generation on first iteration."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        # Mock the agents
        with patch.object(generator, 'code_generator') as mock_code_gen, \
             patch.object(generator, 'test_generator') as mock_test_gen, \
             patch.object(generator, 'cross_validate') as mock_cross_validate:

            # Setup mocks
            code_state = sample_code_generation_state.with_code("function test() {}")
            test_state = code_state.with_tests("describe('test', () => {});")
            validated_state = test_state.with_validation({"passed": True, "score": 95})

            mock_code_gen.generate.return_value = code_state
            mock_test_gen.generate.return_value = test_state
            mock_cross_validate.return_value = validated_state

            # Execute
            result = generator.generate_collaboratively(sample_code_generation_state)

            # Verify calls
            mock_code_gen.generate.assert_called_once()
            mock_test_gen.generate.assert_called_once()
            mock_cross_validate.assert_called_once()

            # Verify result
            assert result.generated_code == validated_state.generated_code
            assert result.generated_tests == validated_state.generated_tests
            assert result.validation_results == validated_state.validation_results
            assert result.feedback['iteration_count'] == 1
            assert len(result.feedback['validation_history']) == 1

    @patch('src.collaborative_generator.log_info')
    def test_generate_collaboratively_with_refinement(self, mock_log_info, service_manager, sample_code_generation_state):
        """Test collaborative generation requiring refinement."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        with patch.object(generator, 'code_generator') as mock_code_gen, \
             patch.object(generator, 'test_generator') as mock_test_gen, \
             patch.object(generator, 'cross_validate') as mock_cross_validate, \
             patch.object(generator, '_refine_code_and_tests') as mock_refine:

            # First validation fails, second succeeds
            code_state = sample_code_generation_state.with_code("function test() {}")
            test_state = code_state.with_tests("describe('test', () => {});")

            failed_validation = test_state.with_validation({"passed": False, "issues": ["test coverage low"]})
            success_validation = test_state.with_validation({"passed": True, "score": 90})

            mock_code_gen.generate.return_value = code_state
            mock_test_gen.generate.return_value = test_state
            mock_cross_validate.side_effect = [failed_validation, success_validation]
            mock_refine.return_value = test_state

            result = generator.generate_collaboratively(sample_code_generation_state)

            # Should have 2 iterations
            assert mock_cross_validate.call_count == 2
            assert mock_refine.call_count == 1
            assert result.feedback['iteration_count'] == 2
            assert len(result.feedback['validation_history']) == 2

    @patch('src.collaborative_generator.log_info')
    def test_generate_collaboratively_max_iterations_reached(self, mock_log_info, service_manager, sample_code_generation_state):
        """Test collaborative generation reaches max iterations without success."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        with patch.object(generator, 'code_generator') as mock_code_gen, \
             patch.object(generator, 'test_generator') as mock_test_gen, \
             patch.object(generator, 'cross_validate') as mock_cross_validate, \
             patch.object(generator, '_refine_code_and_tests') as mock_refine:

            code_state = sample_code_generation_state.with_code("function test() {}")
            test_state = code_state.with_tests("describe('test', () => {});")
            failed_validation = test_state.with_validation({"passed": False, "issues": ["persistent issues"]})

            mock_code_gen.generate.return_value = code_state
            mock_test_gen.generate.return_value = test_state
            mock_cross_validate.return_value = failed_validation
            mock_refine.return_value = test_state

            result = generator.generate_collaboratively(sample_code_generation_state)

            # Should attempt max iterations
            assert mock_cross_validate.call_count == 3  # max_refinement_iterations
            assert mock_refine.call_count == 3
            assert result.feedback['iteration_count'] == 3
            assert result.feedback['max_iterations_exceeded'] is True

    def test_generate_initial_code_success(self, service_manager, sample_code_generation_state):
        """Test successful initial code generation."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        with patch.object(generator.code_generator, 'generate') as mock_generate, \
             patch.object(generator.monitor, 'info') as mock_log:

            expected_state = sample_code_generation_state.with_code("new code")
            mock_generate.return_value = expected_state

            result = generator._generate_initial_code(sample_code_generation_state)

            assert result == expected_state
            mock_log.assert_called_once()

    def test_generate_initial_code_error_handling(self, service_manager, sample_code_generation_state):
        """Test error handling in initial code generation."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        with patch.object(generator.code_generator, 'generate') as mock_generate, \
             patch.object(generator.monitor, 'error') as mock_log:

            mock_generate.side_effect = Exception("Code generation failed")

            with pytest.raises(Exception, match="Code generation failed"):
                generator._generate_initial_code(sample_code_generation_state)

            mock_log.assert_called_once()

    def test_generate_initial_tests_success(self, service_manager, sample_code_generation_state):
        """Test successful initial test generation."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        with patch.object(generator.test_generator, 'generate') as mock_generate, \
             patch.object(generator.monitor, 'info') as mock_log:

            expected_state = sample_code_generation_state.with_tests("new tests")
            mock_generate.return_value = expected_state

            result = generator._generate_initial_tests(sample_code_generation_state)

            assert result == expected_state
            mock_log.assert_called_once()

    def test_generate_initial_tests_error_handling(self, service_manager, sample_code_generation_state):
        """Test error handling in initial test generation."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        with patch.object(generator.test_generator, 'generate') as mock_generate, \
             patch.object(generator.monitor, 'error') as mock_log:

            mock_generate.side_effect = Exception("Test generation failed")

            with pytest.raises(Exception, match="Test generation failed"):
                generator._generate_initial_tests(sample_code_generation_state)

            mock_log.assert_called_once()

    @patch.dict(os.environ, {'PROJECT_ROOT': '/tmp/test'})
    def test_cross_validate_success(self, service_manager, sample_code_generation_state):
        """Test successful cross-validation."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        code_state = sample_code_generation_state.with_code("function test() { return true; }")
        test_state = code_state.with_tests("describe('test', () => { it('works', () => { expect(test()).toBe(true); }); });")

        with patch.object(generator.monitor, 'info') as mock_log:
            combined_state = code_state.with_tests(test_state.generated_tests); result = generator.cross_validate(combined_state)

            # Should have called LLM reasoning
            service_manager.ollama_reasoning.invoke.assert_called_once()

            # Should return combined state with validation
            assert result.generated_code == code_state.generated_code
            assert result.generated_tests == test_state.generated_tests
            assert result.validation_results is not None
            assert result.validation_results.success is True

            # Should log completion
            assert mock_log.call_count >= 1  # completion log

            # Immutability check: input states should not be modified
            assert code_state.generated_code == "function test() { return true; }"
            assert test_state.generated_tests == "describe('test', () => { it('works', () => { expect(test()).toBe(true); }); });"

    def test_cross_validate_error_handling(self, service_manager, sample_code_generation_state):
        """Test error handling in cross-validation."""
        mock_llm_reasoning = service_manager.ollama_reasoning
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        code_state = sample_code_generation_state.with_code("function test() {}")
        test_state = code_state.with_tests("describe('test', () => {});")

        # Mock LLM to raise exception
        mock_llm_reasoning.invoke.side_effect = Exception("LLM validation failed")

        with patch.object(generator.monitor, 'error') as mock_log:
            combined_state = code_state.with_tests(test_state.generated_tests); result = generator.cross_validate(combined_state)

            # Should return error validation result
            assert result.validation_results.success is False
            assert "Cross-validation error" in result.validation_results.errors[0]

            mock_log.assert_called_once()

    def test_parse_validation_response_success(self, service_manager):
        """Test successful parsing of validation response."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        response = json.dumps({
            "passed": True,
            "score": 90,
            "issues": ["minor issue"],
            "recommendations": ["fix this"]
        })

        result = generator._parse_validation_response(response)

        assert result["passed"] is True
        assert result["score"] == 90
        assert result["issues"] == ["minor issue"]
        assert result["recommendations"] == ["fix this"]

    def test_parse_validation_response_malformed_json(self, service_manager):
        """Test parsing of malformed JSON validation response."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        response = "not json at all"

        result = generator._parse_validation_response(response)

        assert result["passed"] is False
        assert result["score"] == 30  # fallback score
        assert "Failed to parse validation response" in result["issues"][0]

    def test_combine_states_with_validation(self, service_manager, sample_code_generation_state):
        """Test combining code and test states with validation results."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        code_state = sample_code_generation_state.with_code("code content")
        test_state = code_state.with_tests("test content")
        validation_result = {"passed": True, "score": 85}

        result = generator._combine_states_with_validation(code_state, test_state, validation_result)

        assert result.generated_code == "code content"
        assert result.generated_tests == "test content"
        assert result.validation_results.success is True
        assert result.issue_url == code_state.issue_url
        assert result.requirements == code_state.requirements

    def test_attempt_refinements_test_refinement(self, service_manager, sample_code_generation_state):
        """Test refinement attempts focusing on test improvements."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        state = sample_code_generation_state.with_validation({"passed": False})
        validation_result = {"issues": ["Add more test cases"], "recommendations": ["Cover edge cases"]}

        with patch.object(generator.test_generator, 'refine_tests') as mock_refine, \
             patch.object(generator, '_cross_validate') as mock_validate:

            refined_state = state.with_validation({"passed": True})
            mock_refine.return_value = refined_state
            mock_validate.return_value = {"passed": True}

            result = generator._attempt_refinements(state, validation_result)

            mock_refine.assert_called_once()
            assert result.generated_code == refined_state.generated_code
            assert result.generated_tests == refined_state.generated_tests
            assert result.validation_results.success == refined_state.validation_results.success

    @patch.dict(os.environ, {'PROJECT_ROOT': '/tmp/test'})
    def test_attempt_refinements_code_refinement(self, service_manager, sample_code_generation_state):
        """Test refinement attempts focusing on code improvements."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        state = sample_code_generation_state.with_validation({"passed": False})
        validation_result = {"issues": ["Code has bugs"], "recommendations": ["Fix implementation"]}

        with patch.object(generator.test_generator, 'refine_tests') as mock_test_refine, \
             patch.object(generator, 'cross_validate') as mock_validate:

            # Test refinement doesn't help
            mock_test_refine.return_value = state
            mock_validate.return_value = state.with_validation({"passed": False})
        
            result = generator._attempt_refinements(state, validation_result)

            # Should attempt test refinement but not succeed
            mock_test_refine.assert_called_once()
            assert result.feedback["refinement_attempted"] is True

    def test_extract_methods_from_code(self, service_manager):
        """Test extracting method names from generated code."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        code = """
        export class TestClass {
            public async testMethod() {}
            private helper() {}
            constructor() {}
            if() {}  // should be filtered out
        }
        function standalone() {}
        """

        methods = generator._extract_methods_from_code(code)

        assert "testMethod" in methods
        assert "helper" in methods
        assert "standalone" in methods
        assert "if" not in methods
        assert "constructor" not in methods

    def test_extract_tested_methods_from_tests(self, service_manager):
        """Test extracting tested method names from test code."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        tests = """
        describe('TestClass', () => {
            it('tests testMethod', () => {
                expect(instance.testMethod()).toBe(true);
            });
            it('tests helper', () => {
                instance.helper();
            });
        });
        """

        methods = generator._extract_tested_methods_from_tests(tests)

        assert "testMethod" in methods
        assert "helper" in methods

    def test_create_refinement_feedback(self, service_manager):
        """Test creating refinement feedback from issues."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        issues = [
            "Untested methods: ['helper']",
            "Tests missing describe blocks",
            "Tests do not reference method 'testMethod'"
        ]

        feedback = generator._create_refinement_feedback(issues)

        assert "Add test cases for all public methods" in feedback
        assert "Structure tests with proper describe blocks" in feedback
        assert "Ensure tests properly reference the generated method" in feedback

    def test_cross_validate_basic_checks(self, service_manager, sample_code_generation_state):
        """Test basic cross-validation checks without LLM."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        # Test with untested methods
        state = sample_code_generation_state.with_code("function test() {}").with_tests("describe('other', () => {});")

        result = generator._cross_validate(state)

        assert result["passed"] is False
        assert len(result["issues"]) > 0
        assert "Untested methods" in str(result["issues"])

    def test_cross_validate_missing_test_structure(self, service_manager, sample_code_generation_state):
        """Test cross-validation with missing test structure."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        # Test with missing describe blocks
        state = sample_code_generation_state.with_code("function test() {}").with_tests("it('works', () => {});")

        result = generator._cross_validate(state)

        assert result["passed"] is False
        assert any("describe blocks" in issue for issue in result["issues"])

    def test_cross_validate_missing_method_reference(self, service_manager, sample_code_generation_state):
        """Test cross-validation with missing method/command references."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        # State with method_name but tests don't reference it
        state = sample_code_generation_state.with_code("function myMethod() {}").with_tests("describe('test', () => { it('works', () => {}); });")
        state = sample_code_generation_state.with_code("function myMethod() {}", "myMethod", "my-cmd").with_tests("describe('test', () => { it('works', () => {}); });")

        result = generator._cross_validate(state)

        assert result["passed"] is False
        assert any("not reference" in issue for issue in result["issues"])

    def test_refine_code_and_tests_success(self, service_manager, sample_code_generation_state):
        """Test successful refinement of code and tests."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        state = sample_code_generation_state.with_validation({"passed": False, "issues": ["Add more tests"]})

        with patch.object(generator.test_generator, 'refine_tests') as mock_refine, \
             patch.object(generator, '_cross_validate') as mock_validate:

            refined_state = state.with_validation({"passed": True})
            mock_refine.return_value = refined_state
            mock_validate.return_value = {"passed": True}

            result = generator._refine_code_and_tests(state, {"issues": ["Add more tests"]})

            assert result.generated_code == refined_state.generated_code
            assert result.generated_tests == refined_state.generated_tests
            assert result.validation_results.success == refined_state.validation_results.success

    def test_refine_code_and_tests_failure(self, service_manager, sample_code_generation_state):
        """Test refinement failure handling."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        state = sample_code_generation_state.with_validation({"passed": False})

        with patch.object(generator.test_generator, 'refine_tests') as mock_refine, \
             patch.object(generator.monitor, 'error') as mock_log:

            mock_refine.side_effect = Exception("Refinement failed")

            result = generator._refine_code_and_tests(state, {"issues": ["test issues"]})

            assert result.feedback["refinement_failed"] == "Refinement failed"
            mock_log.assert_called_once()

    @patch('src.collaborative_generator.get_circuit_breaker')
    def test_circuit_breaker_execution(self, mock_get_circuit_breaker, service_manager, sample_code_generation_state):
        """Test that circuit breaker wraps execution."""
        mock_circuit_breaker = MagicMock()
        mock_get_circuit_breaker.return_value = mock_circuit_breaker

        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        with patch.object(generator, '_generate_initial_code') as mock_code_gen, \
             patch.object(generator, '_generate_initial_tests') as mock_test_gen, \
             patch.object(generator, 'cross_validate') as mock_validate:

            mock_code_gen.return_value = sample_code_generation_state
            mock_test_gen.return_value = sample_code_generation_state
            mock_validate.return_value = sample_code_generation_state.with_validation({"passed": True})

            generator.generate_collaboratively(sample_code_generation_state)

            # Circuit breaker should have been called
            assert mock_circuit_breaker.call.called

    def test_structured_logging(self, service_manager, sample_code_generation_state):
        """Test structured logging functionality."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        with patch.object(generator.monitor, 'info') as mock_info, \
             patch.object(generator.monitor, 'warning') as mock_warning, \
             patch.object(generator.monitor, 'error') as mock_error:

            # Test info logging
            generator._log_structured("info", "test_event", {"key": "value"})
            mock_info.assert_called_with("test_event", {"key": "value"})

            # Test warning logging
            generator._log_structured("warning", "test_warning", {"issue": "problem"})
            mock_warning.assert_called_with("test_warning", {"issue": "problem"})

            # Test error logging
            generator._log_structured("error", "test_error", {"error": "failure"})
            mock_error.assert_called_with("test_error", {"error": "failure"})

    def test_error_recovery_in_generate_collaboratively(self, service_manager, sample_code_generation_state):
        """Test error recovery in main generation method."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        with patch.object(generator, 'circuit_breaker') as mock_circuit_breaker, \
             patch.object(generator.monitor, 'error') as mock_log:

            mock_circuit_breaker.call.side_effect = Exception("Circuit breaker failure")

            with pytest.raises(Exception, match="Circuit breaker failure"):
                generator.generate_collaboratively(sample_code_generation_state)

            mock_log.assert_called_once()

    def test_empty_code_generation(self, service_manager, sample_code_generation_state):
        """Test handling of empty generated code."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        state = sample_code_generation_state.with_code("").with_tests("describe('test', () => {});")

        result = generator._cross_validate(state)

        assert result["passed"] is False
        assert result["code_methods"] == []

    def test_empty_test_generation(self, service_manager, sample_code_generation_state):
        """Test handling of empty generated tests."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        state = sample_code_generation_state.with_code("function test() {}").with_tests("")

        result = generator._cross_validate(state)

        assert result["passed"] is False
        assert "describe(" not in result["issues"][0] or "test cases" in result["issues"][0]

    def test_malformed_validation_prompt_creation(self, service_manager, sample_code_generation_state):
        """Test validation prompt creation with various inputs."""
        generator = CollaborativeGenerator(service_manager.ollama_reasoning)

        code_state = sample_code_generation_state.with_code("code")
        test_state = code_state.with_tests("tests")

        combined_state = code_state.with_tests(test_state.generated_tests); prompt = generator._create_validation_prompt(combined_state)

        assert "Generated Code:" in prompt
        assert "Generated Tests:" in prompt
        assert "Method Name:" in prompt
        assert "Command ID:" in prompt
        assert code_state.generated_code in prompt
        assert test_state.generated_tests in prompt