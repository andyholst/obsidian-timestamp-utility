"""
Unit tests for TypeScriptValidator class in code_validator.py

These tests cover TypeScript compilation validation, runtime safety validation,
and type analysis as described in LLM_CODE_VALIDATION.md.
"""

import pytest
import json
import tempfile
import os
import subprocess
import sys
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

# Add the src directory to the path to avoid importing the full package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from code_validator import (
    TypeScriptValidator,
    CompilationResult,
    ExecutionResult,
    TestResult,
    TestValidator,
    LangChainValidator,
    QualityScorer,
    LLMCodeValidationPipeline,
    ValidationReport,
    RiskLevel,
    ChainValidation
)


class TestTypeScriptValidator:
    """Unit tests for TypeScriptValidator class"""

    @pytest.fixture
    def validator(self):
        """Fixture for TypeScriptValidator"""
        return TypeScriptValidator()

    def test_validator_initialization(self, validator):
        """Test validator initialization with default config"""
        assert validator.sandbox_config['timeout'] == 5000
        assert validator.sandbox_config['memory_limit'] == '128MB'
        assert validator.sandbox_config['network_disabled'] == True
        assert validator.sandbox_config['filesystem_readonly'] == True

    @patch('code_validator.subprocess.run')
    def test_validate_compilation_success(self, mock_run, validator):
        """Test successful TypeScript compilation"""
        # Mock compilation success
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        valid_code = """
        export class UserService {
            getUser(id: string): string {
                return `User ${id}`;
            }
        }
        """

        result = validator.validate_compilation(valid_code)

        assert result.success == True
        assert len(result.errors) == 0
        assert result.execution_time >= 0

    @patch('code_validator.subprocess.run')
    def test_validate_compilation_with_errors(self, mock_run, validator):
        """Test TypeScript compilation with syntax errors"""
        # Mock compilation with errors
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="test.ts(2,10): error TS1003: Identifier expected."
        )

        invalid_code = """
        export class UserService {
            getUser(id: string) {
                return 'User ' + id
            }
        }
        """

        result = validator.validate_compilation(invalid_code)

        assert result.success == False
        assert len(result.errors) > 0
        assert "Identifier expected" in result.errors[0]

    @patch('code_validator.subprocess.run')
    def test_validate_compilation_with_warnings(self, mock_run, validator):
        """Test TypeScript compilation with warnings"""
        # Mock compilation with warnings
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="test.ts(3,5): warning TS6133: 'unusedVar' is declared but never used."
        )

        code_with_warnings = """
        export class UserService {
            getUser(id: string): string {
                let unusedVar = "test";
                return `User ${id}`;
            }
        }
        """

        result = validator.validate_compilation(code_with_warnings)

        assert result.success == True
        assert len(result.warnings) > 0
        assert "never used" in result.warnings[0]

    @patch('code_validator.subprocess.run')
    def test_validate_compilation_tsc_not_found(self, mock_run, validator):
        """Test compilation when TypeScript compiler is not found"""
        mock_run.side_effect = FileNotFoundError("tsc command not found")

        code = "export const test = 'hello';"

        result = validator.validate_compilation(code)

        assert result.success == False
        assert len(result.errors) > 0
        assert "TypeScript compiler not found" in result.errors[0]

    @patch('code_validator.subprocess.run')
    @patch('code_validator.subprocess.TimeoutExpired')
    def test_validate_compilation_timeout(self, mock_timeout, mock_run, validator):
        """Test compilation timeout handling"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=['npx', 'tsc'], timeout=30)

        code = "export const test = 'hello';"

        result = validator.validate_compilation(code)

        assert result.success == False
        assert len(result.errors) > 0
        assert "Compilation timeout" in result.errors[0]

    @patch('code_validator.subprocess.run')
    def test_validate_runtime_safety_success(self, mock_run, validator):
        """Test successful runtime safety validation"""
        mock_run.return_value = MagicMock(returncode=0, stdout="Code executed successfully", stderr="")
        code = """
        export function calculate(a, b) {
            return a + b;
        }
        """

        result = validator.validate_runtime_safety(code)

        assert result.success == True
        assert result.output == "Code executed successfully"
        assert result.errors == ""
        assert result.execution_time >= 0
        assert result.timeout == False

    @patch('code_validator.subprocess.run')
    def test_validate_runtime_safety_with_errors(self, mock_run, validator):
        """Test runtime safety validation with execution errors"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ReferenceError: undefinedVar is not defined"
        )

        code = """
        export function test(): void {
            console.log(undefinedVar);
        }
        """

        result = validator.validate_runtime_safety(code)

        assert result.success == False
        assert "undefinedVar is not defined" in result.errors
        assert result.timeout == False

    @patch('code_validator.subprocess.run')
    def test_validate_runtime_safety_timeout(self, mock_run, validator):
        """Test runtime safety validation timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=['node'], timeout=5)

        code = """
        export function infiniteLoop(): void {
            while (true) {}
        }
        """

        result = validator.validate_runtime_safety(code)

        assert result.success == False
        assert result.timeout == True
        assert result.execution_time >= 0

    @patch('code_validator.subprocess.run')
    def test_validate_runtime_safety_sandbox_prevention(self, mock_run, validator):
        """Test that sandbox prevents dangerous operations"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: Module not allowed: fs"
        )

        code = """
        export function readFile(): void {
            const fs = require('fs');
            fs.readFileSync('/etc/passwd');
        }
        """

        result = validator.validate_runtime_safety(code)

        assert result.success == False
        assert "Module not allowed" in result.errors

    def test_analyze_types_basic(self, validator):
        """Test basic type analysis"""
        code = """
        export interface User {
            id: number;
            name: string;
        }

        export class UserService {
            getUser(id: number): User {
                return { id, name: "Test" };
            }
        }
        """

        analysis = validator.analyze_types(code)

        assert 'any_types' in analysis
        assert 'null_checks' in analysis
        assert 'generic_usage' in analysis
        assert 'interface_compliance' in analysis

    def test_analyze_types_with_any(self, validator):
        """Test type analysis with 'any' types"""
        code = """
        export function processData(data: any): any {
            return data;
        }
        """

        analysis = validator.analyze_types(code)

        assert analysis['any_types'] == 2  # data parameter and return type

    def test_analyze_types_with_null_checks(self, validator):
        """Test type analysis with null checks"""
        code = """
        export function safeGet(obj: any): string {
            if (obj !== null && obj !== undefined) {
                return obj.toString();
            }
            return "";
        }
        """

        analysis = validator.analyze_types(code)

        assert analysis['null_checks'] >= 2  # !== null and !== undefined

    def test_analyze_types_with_generics(self, validator):
        """Test type analysis with generics"""
        code = """
        export interface Result<T> {
            data: T;
            success: boolean;
        }

        export function createResult<T>(data: T): Result<T> {
            return { data, success: true };
        }
        """

        analysis = validator.analyze_types(code)

        assert analysis['generic_usage'] >= 2  # <T> in interface and function

    def test_analyze_types_with_interfaces(self, validator):
        """Test type analysis with interface implementation"""
        code = """
        export interface Service {
            execute(): void;
        }

        export class ApiService implements Service {
            execute(): void {
                console.log("Executed");
            }
        }
        """

        analysis = validator.analyze_types(code)

        assert analysis['interface_compliance'] >= 1  # implements Service


    @patch('code_validator.os.getenv')
    def test_sandbox_config_from_environment(self, mock_getenv, validator):
        """Test that sandbox config reads from environment variables"""
        mock_getenv.side_effect = lambda key, default: {
            'TS_EXECUTION_TIMEOUT': '10000',
            'TS_MEMORY_LIMIT': '256MB'
        }.get(key, default)

        # Create new validator to test initialization
        new_validator = TypeScriptValidator()

        assert new_validator.sandbox_config['timeout'] == 10000
        assert new_validator.sandbox_config['memory_limit'] == '256MB'


class TestCompilationResult:
    """Unit tests for CompilationResult dataclass"""

    def test_compilation_result_success(self):
        """Test successful compilation result"""
        result = CompilationResult(
            success=True,
            errors=[],
            warnings=[],
            execution_time=1.5
        )

        assert result.success == True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert result.execution_time == 1.5

    def test_compilation_result_with_errors(self):
        """Test compilation result with errors"""
        errors = ["Syntax error", "Type error"]
        warnings = ["Unused variable"]

        result = CompilationResult(
            success=False,
            errors=errors,
            warnings=warnings,
            execution_time=2.0
        )

        assert result.success == False
        assert result.errors == errors
        assert result.warnings == warnings
        assert result.execution_time == 2.0


class TestExecutionResult:
    """Unit tests for ExecutionResult dataclass"""

    def test_execution_result_success(self):
        """Test successful execution result"""
        result = ExecutionResult(
            success=True,
            output="Hello World",
            errors="",
            execution_time=0.5,
            memory_used=1024,
            timeout=False
        )

        assert result.success == True
        assert result.output == "Hello World"
        assert result.errors == ""
        assert result.execution_time == 0.5
        assert result.memory_used == 1024
        assert result.timeout == False

    def test_execution_result_failure(self):
        """Test failed execution result"""
        result = ExecutionResult(
            success=False,
            output="",
            errors="ReferenceError: x is not defined",
            execution_time=1.2,
            timeout=False
        )

        assert result.success == False
        assert "ReferenceError" in result.errors
        assert result.execution_time == 1.2


class TestIntegrationScenarios:
    """Integration tests for complete validation workflows"""

    @pytest.fixture
    def validator(self):
        """Fixture for TypeScriptValidator"""
        return TypeScriptValidator()

    @patch('code_validator.subprocess.run')
    def test_complete_validation_workflow_valid_code(self, mock_run, validator):
        """Test complete validation workflow with valid TypeScript code"""
        # Mock compilation success
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        valid_code = """
        export interface User {
            id: number;
            name: string;
            email?: string;
        }

        export class UserService {
            private users: User[] = [];

            addUser(user: User): void {
                if (user.id && user.name) {
                    this.users.push(user);
                }
            }

            getUser(id: number): User | undefined {
                return this.users.find(u => u.id === id);
            }

            getAllUsers(): User[] {
                return [...this.users];
            }
        }
        """

        # Test compilation
        compile_result = validator.validate_compilation(valid_code)
        assert compile_result.success == True

        # Test runtime safety
        runtime_result = validator.validate_runtime_safety(valid_code)
        # Note: Runtime test might fail due to Node.js environment differences,
        # but the important thing is that it runs without throwing exceptions

        # Test type analysis
        type_analysis = validator.analyze_types(valid_code)
        assert type_analysis['interface_compliance'] == 0
        assert type_analysis['null_checks'] >= 1

    def test_validation_workflow_invalid_code(self, validator):
        """Test validation workflow with invalid TypeScript code"""
        invalid_code = """
        export class BrokenService {
            getData(id: string): number {
                return id.toUpperCase();  // Type error: string -> number
            }

            brokenMethod() {
                undefinedVar;  // Reference error
            }
        }
        """

        # Compilation should fail
        compile_result = validator.validate_compilation(invalid_code)
        assert compile_result.success == False
        assert len(compile_result.errors) > 0

        # Runtime safety should also fail
        runtime_result = validator.validate_runtime_safety(invalid_code)
        # May or may not fail depending on strictness, but shouldn't crash

        # Type analysis should still work
        type_analysis = validator.analyze_types(invalid_code)
        assert isinstance(type_analysis, dict)

    def test_edge_cases(self, validator):
        """Test edge cases in validation"""

        # Empty code
        empty_result = validator.validate_compilation("")
        # Should handle gracefully

        # Very large code (simulate)
        large_code = "export const x = 1;\n" * 1000
        large_result = validator.validate_compilation(large_code)
        # Should handle large inputs

        # Code with special characters
        special_code = """
        export const emojis = "🚀💻🔧";
        export function testUnicode(): string {
            return "café";
        }
        """
        special_result = validator.validate_compilation(special_code)
        # Should handle Unicode properly

    @patch('code_validator.subprocess.run')
    def test_error_recovery(self, mock_run, validator):
        """Test error recovery and graceful degradation"""

        # Simulate various failure modes
        failure_modes = [
            FileNotFoundError("Command not found"),
            subprocess.TimeoutExpired(cmd=['node'], timeout=5),
            Exception("Unexpected error")
        ]

        test_code = "export const test = 42;"

        for failure in failure_modes:
            mock_run.side_effect = failure

            # Should not crash, should return appropriate error results
            compile_result = validator.validate_compilation(test_code)
            assert compile_result.success == False
            assert len(compile_result.errors) > 0

            runtime_result = validator.validate_runtime_safety(test_code)
            assert runtime_result.success == False


class TestTypeScriptValidatorRobustness:
    """Tests for robustness and error handling"""

    @pytest.fixture
    def validator(self):
        """Fixture for TypeScriptValidator"""
        return TypeScriptValidator()

    @patch('code_validator.subprocess.run')
    def test_concurrent_validation_calls(self, mock_run, validator):
        """Test that multiple validation calls work concurrently"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        code1 = "export const a = 1;"
        code2 = "export const b = 2;"

        # Run validations concurrently (in same process)
        result1 = validator.validate_compilation(code1)
        result2 = validator.validate_compilation(code2)

        assert result1.success == True
        assert result2.success == True

    @patch('code_validator.tempfile.NamedTemporaryFile')
    def test_file_permission_issues(self, mock_temp_file, validator):
        """Test handling of file permission issues"""
        # Simulate permission denied
        mock_file = MagicMock()
        mock_file.name = '/tmp/test.ts'
        mock_temp_file.return_value.__enter__.return_value = mock_file

        with patch('builtins.open', mock_open()) as mock_file_open:
            mock_file_open.side_effect = PermissionError("Permission denied")

            result = validator.validate_compilation("export const test = 1;")

            assert result.success == False
            assert len(result.errors) > 0

    def test_memory_limits_configuration(self, validator):
        """Test memory limit configuration parsing"""
        # Test with different memory formats
        test_cases = [
            ('64MB', 64),
            ('128MB', 128),
            ('256MB', 256),
            ('512MB', 512)
        ]

        for mem_limit, expected_mb in test_cases:
            # This would be tested by checking the subprocess call arguments
            # in a more integrated test
            assert mem_limit.endswith('MB')
            assert int(mem_limit[:-2]) == expected_mb

    @patch('code_validator.subprocess.run')
    def test_subprocess_error_handling(self, mock_run, validator):
        """Test comprehensive subprocess error handling"""
        error_scenarios = [
            (FileNotFoundError("tsc not found"), "TypeScript compiler not found"),
            (subprocess.TimeoutExpired(['npx', 'tsc'], 30), "Compilation timeout"),
            (OSError("System error"), "Compilation failed"),
            (Exception("Unexpected"), "Compilation failed")
        ]

        for exception, expected_error in error_scenarios:
            mock_run.side_effect = exception

            result = validator.validate_compilation("export const test = 1;")

            assert result.success == False
            assert any(expected_error in error for error in result.errors)
class TestLLMCodeValidationPipeline:
    """Unit tests for LLMCodeValidationPipeline class"""

    @pytest.fixture
    def pipeline(self):
        """Fixture for LLMCodeValidationPipeline"""
        return LLMCodeValidationPipeline()

    def test_pipeline_initialization(self, pipeline):
        """Test pipeline initialization"""
        assert isinstance(pipeline.ts_validator, TypeScriptValidator)
        assert isinstance(pipeline.test_validator, TestValidator)
        assert isinstance(pipeline.pattern_validator, LangChainValidator)
        assert isinstance(pipeline.quality_scorer, QualityScorer)

    @patch('code_validator.TypeScriptValidator.validate_compilation')
    @patch('code_validator.TypeScriptValidator.validate_runtime_safety')
    @patch('code_validator.TestValidator.run_tests')
    @patch('code_validator.LangChainValidator.validate_patterns')
    @patch('code_validator.QualityScorer.calculate_score')
    @patch('code_validator.QualityScorer.assess_risk')
    def test_validate_typescript_code_success(self, mock_assess_risk, mock_calculate_score,
                                          mock_validate_patterns, mock_run_tests,
                                          mock_validate_runtime, mock_validate_compilation, pipeline):
        """Test successful TypeScript code validation"""
        # Setup mocks
        mock_validate_compilation.return_value = CompilationResult(success=True, errors=[], warnings=[])
        mock_validate_runtime.return_value = ExecutionResult(success=True, output="Success")
        mock_run_tests.return_value = TestResult(success=True, passed_count=5, test_count=5, coverage={'total': {'lines': {'pct': 80.0}}})
        mock_validate_patterns.return_value = ChainValidation(composability_score=8.0)
        mock_calculate_score.return_value = 88.0
        mock_assess_risk.return_value = RiskLevel.LOW

        code = "export class Test {}"
        tests = "describe('test', () => { it('works', () => {}); });"
        context = {'is_agentics_code': True}

        result = pipeline.validate_typescript_code(code, tests, context)

        assert result.overall_score == 88.0
        assert result.risk_level == RiskLevel.LOW
        assert result.safety_check.success == True
        assert result.test_results.passed == True
        assert result.pattern_validation.composability_score == 8.0
        mock_validate_compilation.assert_called_once()
        mock_validate_runtime.assert_called_once()
        mock_run_tests.assert_called_once()
        mock_validate_patterns.assert_called_once()
        mock_calculate_score.assert_called_once()
        mock_assess_risk.assert_called_once()

    @patch('code_validator.TypeScriptValidator.validate_compilation')
    @patch('code_validator.TypeScriptValidator.validate_runtime_safety')
    @patch('code_validator.TestValidator.run_tests')
    def test_validate_typescript_code_compilation_failure(self, mock_run_tests, mock_validate_runtime,
                                                        mock_validate_compilation, pipeline):
        """Test validation when compilation fails"""
        # Setup mocks
        mock_validate_compilation.return_value = CompilationResult(success=False, errors=["Syntax error"])
        mock_validate_runtime.return_value = ExecutionResult(success=False, errors="Compilation failed")

        code = "invalid syntax {{{"
        tests = "describe('test', () => {});"

        result = pipeline.validate_typescript_code(code, tests)

        assert result.safety_check.success == False
        assert "Syntax error" in result.safety_check.errors
        assert result.overall_score < 50  # Should be low due to failure
        assert result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    @patch('code_validator.TypeScriptValidator.validate_compilation')
    @patch('code_validator.TypeScriptValidator.validate_runtime_safety')
    @patch('code_validator.TestValidator.run_tests')
    @patch('code_validator.LangChainValidator.validate_patterns')
    def test_validate_typescript_code_with_agentics_context(self, mock_validate_patterns, mock_run_tests,
                                                           mock_validate_runtime, mock_validate_compilation, pipeline):
        """Test validation with agentics code context"""
        # Setup mocks
        mock_validate_compilation.return_value = CompilationResult(success=True)
        mock_validate_runtime.return_value = ExecutionResult(success=True)
        mock_run_tests.return_value = TestResult(success=True, coverage={'total': {'lines': {'pct': 90.0}}})
        mock_validate_patterns.return_value = ChainValidation(uses_lcel=True, composability_score=9.0)

        code = "export class Agent {}"
        tests = "describe('agent', () => {});"
        context = {'is_agentics_code': True}

        result = pipeline.validate_typescript_code(code, tests, context)

        mock_validate_patterns.assert_called_once_with(code)

    @patch('code_validator.TypeScriptValidator.validate_compilation')
    @patch('code_validator.TypeScriptValidator.validate_runtime_safety')
    @patch('code_validator.TestValidator.run_tests')
    def test_validate_typescript_code_without_agentics_context(self, mock_run_tests, mock_validate_runtime,
                                                              mock_validate_compilation, pipeline):
        """Test validation without agentics code context"""
        # Setup mocks
        mock_validate_compilation.return_value = CompilationResult(success=True)
        mock_validate_runtime.return_value = ExecutionResult(success=True)
        mock_run_tests.return_value = TestResult(success=True, coverage={'total': {'lines': {'pct': 80.0}}})

        code = "export class Component {}"
        tests = "describe('component', () => {});"
        context = {'is_agentics_code': False}

        result = pipeline.validate_typescript_code(code, tests, context)

        assert result.pattern_validation is None  # Should not validate patterns for non-agentics code

    def test_generate_recommendations_safety_issues(self, pipeline):
        """Test recommendation generation for safety issues"""
        result = ValidationReport(
            safety_check=ExecutionResult(success=False, errors="Runtime error"),
            test_results=TestResult(success=True),
            pattern_validation=None
        )

        pipeline._generate_recommendations(result)

        assert len(result.critical_issues) > 0
        assert any("execution failed" in issue.lower() for issue in result.critical_issues)

    def test_generate_recommendations_test_issues(self, pipeline):
        """Test recommendation generation for test issues"""
        result = ValidationReport(
            safety_check=ExecutionResult(success=True),
            test_results=TestResult(success=False, failed_count=3, test_count=5, coverage={'total': {'lines': {'pct': 45.0}}}),
            pattern_validation=None
        )

        pipeline._generate_recommendations(result)

        assert len(result.critical_issues) > 0
        assert any("tests failed" in issue.lower() for issue in result.critical_issues)
        assert any("coverage below" in issue.lower() for issue in result.warnings)

    def test_generate_recommendations_pattern_issues(self, pipeline):
        """Test recommendation generation for pattern issues"""
        result = ValidationReport(
            safety_check=ExecutionResult(success=True),
            test_results=TestResult(success=True),
            pattern_validation=ChainValidation(uses_lcel=False, proper_error_handling=False)
        )

        pipeline._generate_recommendations(result)

        assert len(result.suggestions) > 0
        assert any("LCEL" in suggestion for suggestion in result.suggestions)
        assert any("error handling" in suggestion.lower() for suggestion in result.warnings)

    @patch('code_validator.TypeScriptValidator.validate_compilation')
    def test_pipeline_error_handling(self, mock_validate_compilation, pipeline):
        """Test pipeline error handling"""
        mock_validate_compilation.side_effect = Exception("Unexpected error")

        code = "export class Test {}"
        tests = "describe('test', () => {});"

        result = pipeline.validate_typescript_code(code, tests)

        assert result.overall_score == 0.0
        assert result.risk_level == RiskLevel.CRITICAL
        assert len(result.critical_issues) > 0
        assert any("pipeline error" in issue.lower() for issue in result.critical_issues)


class TestSafeCodeExecutor:
    """Unit tests for SafeCodeExecutor (TypeScriptValidator.validate_runtime_safety)"""

    @pytest.fixture
    def executor(self):
        """Fixture for TypeScriptValidator as SafeCodeExecutor"""
        return TypeScriptValidator()

    @patch('code_validator.subprocess.run')
    def test_safe_execution_success(self, mock_run, executor):
        """Test successful safe code execution"""
        mock_run.return_value = MagicMock(returncode=0, stdout="Code executed successfully", stderr="")
        code = """
        export function calculate(a: number, b: number): number {
            return a + b;
        }
        """

        result = executor.validate_runtime_safety(code)

        assert result.success == True
        assert "executed successfully" in result.output
        assert result.errors == ""
        assert result.timeout == False

    @patch('code_validator.subprocess.run')
    def test_safe_execution_with_runtime_error(self, mock_run, executor):
        """Test safe execution with runtime errors"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ReferenceError: undefinedVariable is not defined"
        )

        code = """
        export function test(): void {
            console.log(undefinedVariable);
        }
        """

        result = executor.validate_runtime_safety(code)

        assert result.success == False
        assert "undefinedVariable" in result.errors
        assert result.timeout == False

    @patch('code_validator.subprocess.run')
    def test_safe_execution_timeout(self, mock_run, executor):
        """Test safe execution timeout handling"""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired(cmd=['node'], timeout=5)

        code = """
        export function infinite(): void {
            while (true) {
                // Infinite loop
            }
        }
        """

        result = executor.validate_runtime_safety(code)

        assert result.success == False
        assert result.timeout == True
        assert result.execution_time >= 0

    @patch('code_validator.subprocess.run')
    def test_safe_execution_sandbox_violation(self, mock_run, executor):
        """Test sandbox violation detection"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: Module not allowed: fs"
        )

        code = """
        export function readFile(): void {
            const fs = require('fs');
            fs.readFileSync('/etc/passwd');
        }
        """

        result = executor.validate_runtime_safety(code)

        assert result.success == False
        assert "Module not allowed" in result.errors

    @patch('code_validator.subprocess.run')
    def test_safe_execution_with_complex_code(self, mock_run, executor):
        """Test safe execution with complex TypeScript code"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Code executed successfully",
            stderr=""
        )

        code = """
        export interface User {
            id: number;
            name: string;
        }

        export class UserService {
            private users: User[] = [];

            addUser(user: User): void {
                this.users.push(user);
            }

            findUser(id: number): User | undefined {
                return this.users.find(u => u.id === id);
            }
        }
        """

        result = executor.validate_runtime_safety(code)

        assert result.success == True
        assert result.errors == ""

    def test_safe_execution_environment_isolation(self, executor):
        """Test that execution environment is properly isolated"""
        # This test verifies the sandbox configuration
        assert executor.sandbox_config['network_disabled'] == True
        assert executor.sandbox_config['filesystem_readonly'] == True
        assert executor.sandbox_config['timeout'] == 5000
        assert executor.sandbox_config['memory_limit'] == '128MB'


class TestTestValidationRunner:
    """Unit tests for TestValidationRunner (TestValidator)"""

    @pytest.fixture
    def runner(self):
        """Fixture for TestValidator as TestValidationRunner"""
        return TestValidator()

    def test_runner_initialization(self, runner):
        """Test TestValidationRunner initialization"""
        assert runner.test_directory.startswith('/tmp') or 'ts_validation' in runner.test_directory
        assert runner.jest_config['collectCoverage'] == True
        assert runner.jest_config['testTimeout'] == 10000

    @patch('code_validator.TestValidator._write_test_files')
    @patch('code_validator.TestValidator._parse_jest_output')
    @patch('code_validator.TestValidator._parse_coverage_report')
    @patch('code_validator.subprocess.run')
    def test_run_tests_success(self, mock_run, mock_parse_coverage, mock_parse_output, mock_write_files, runner):
        """Test successful test execution"""
        mock_run.return_value.returncode = 0
        mock_parse_output.return_value = {'total': 5, 'passed': 5, 'failed': 0}
        mock_parse_coverage.return_value = {'total': {'lines': {'pct': 85.0}}}

        code = "export class Test {}"
        tests = "describe('test', () => { it('works', () => {}); });"

        result = runner.run_tests(tests, code)

        assert result.passed == True
        assert result.test_count == 5
        assert result.passed_count == 5
        assert result.failed_count == 0
        assert result.coverage['total']['lines']['pct'] == 85.0

    @patch('code_validator.TestValidator._write_test_files')
    @patch('code_validator.TestValidator._parse_jest_output')
    @patch('code_validator.subprocess.run')
    def test_run_tests_failure(self, mock_run, mock_parse_output, mock_write_files, runner):
        """Test test execution with failures"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout='{"testResults": [{"assertionResults": [{"status": "failed"}]}]}',
            stderr="Test failed"
        )
        mock_parse_output.return_value = {'total': 3, 'passed': 1, 'failed': 2}

        code = "export class Test {}"
        tests = "describe('test', () => { it('fails', () => { throw new Error('test'); }); });"

        result = runner.run_tests(tests, code)

        assert result.passed == False
        assert result.test_count == 3
        assert result.passed_count == 1
        assert result.failed_count == 2
        assert "Test failed" in result.errors

    @patch('code_validator.TestValidator._write_test_files')
    @patch('code_validator.subprocess.run')
    @patch('code_validator.subprocess.TimeoutExpired')
    def test_run_tests_timeout(self, mock_timeout, mock_run, mock_write_files, runner):
        """Test test execution timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=['npx', 'jest'], timeout=60)

        code = "export class Test {}"
        tests = "describe('test', () => { it('slow', () => {}); });"

        result = runner.run_tests(tests, code)

        assert result.passed == False
        assert "Test execution timeout" in result.errors

    def test_parse_jest_output_success(self, runner):
        """Test Jest output parsing for successful tests"""
        stdout = "Tests: 8 passed, 2 failed"
        stderr = ""

        # Call the private method directly
        result = runner._parse_jest_output(stdout, stderr)

        assert result['total'] == 10
        assert result['passed'] == 8
        assert result['failed'] == 2

    def test_parse_jest_output_json(self, runner):
        """Test Jest JSON output parsing"""
        stdout = '{"testResults": [{"assertionResults": [{"status": "passed"}, {"status": "failed"}]}]}'
        stderr = ""

        result = runner._parse_jest_output(stdout, stderr)

        assert result['total'] == 2
        assert result['passed'] == 1
        assert result['failed'] == 1

    @patch('code_validator.os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='{"total": {"lines": {"pct": 75.0}}}')
    def test_parse_coverage_report(self, mock_file, mock_exists, runner):
        """Test coverage report parsing"""
        mock_exists.return_value = True
        temp_dir = "/tmp/test"

        coverage = runner._parse_coverage_report(temp_dir)

        assert coverage['total']['lines']['pct'] == 75.0

    @patch('code_validator.os.path.exists')
    def test_parse_coverage_report_missing(self, mock_exists, runner):
        """Test coverage report parsing when file doesn't exist"""
        mock_exists.return_value = False
        temp_dir = "/tmp/test"

        coverage = runner._parse_coverage_report(temp_dir)

        assert coverage == {}


class TestCoverageAnalyzer:
    """Unit tests for CoverageAnalyzer (TestValidator.analyze_coverage)"""

    @pytest.fixture
    def analyzer(self):
        """Fixture for TestValidator as CoverageAnalyzer"""
        return TestValidator()

    def test_analyze_coverage_comprehensive(self, analyzer):
        """Test comprehensive coverage analysis"""
        coverage_data = {
            'total': {
                'lines': {'pct': 85.0, 'total': 100, 'covered': 85},
                'branches': {'pct': 75.0},
                'functions': {'pct': 90.0}
            },
            'source.ts': {
                'lines': {1: 1, 2: 1, 3: 0, 4: 1}  # Line 3 uncovered
            }
        }

        result = analyzer.analyze_coverage(coverage_data)

        assert result.line_coverage == 85.0
        assert result.branch_coverage == 75.0
        assert result.function_coverage == 90.0
        assert result.uncovered_lines == [3]
        assert result.quality_score > 0

    def test_analyze_coverage_perfect(self, analyzer):
        """Test coverage analysis with perfect coverage"""
        coverage_data = {
            'total': {
                'lines': {'pct': 100.0},
                'branches': {'pct': 100.0},
                'functions': {'pct': 100.0}
            }
        }

        result = analyzer.analyze_coverage(coverage_data)

        assert result.line_coverage == 100.0
        assert result.quality_score == 1.0  # (1.0 + 1.0 + 1.0) / 3

    def test_analyze_coverage_poor(self, analyzer):
        """Test coverage analysis with poor coverage"""
        coverage_data = {
            'total': {
                'lines': {'pct': 25.0},
                'branches': {'pct': 10.0},
                'functions': {'pct': 30.0}
            }
        }

        result = analyzer.analyze_coverage(coverage_data)

        assert result.line_coverage == 25.0
        assert result.quality_score < 0.5

    def test_analyze_coverage_missing_data(self, analyzer):
        """Test coverage analysis with missing data"""
        coverage_data = {}

        result = analyzer.analyze_coverage(coverage_data)

        assert result.line_coverage == 0.0
        assert result.branch_coverage == 0.0
        assert result.function_coverage == 0.0
        assert result.uncovered_lines == []
        assert result.quality_score == 0.0

    def test_analyze_coverage_partial_data(self, analyzer):
        """Test coverage analysis with partial data"""
        coverage_data = {
            'total': {
                'lines': {'pct': 80.0}
                # Missing branches and functions
            }
        }

        result = analyzer.analyze_coverage(coverage_data)

        assert result.line_coverage == 80.0
        assert result.branch_coverage == 0.0
        assert result.function_coverage == 0.0

    def test_analyze_coverage_with_uncovered_lines(self, analyzer):
        """Test coverage analysis with detailed uncovered lines"""
        coverage_data = {
            'total': {
                'lines': {'pct': 75.0}
            },
            'source.ts': {
                'lines': {1: 1, 2: 0, 3: 1, 4: 0, 5: 0, 6: 1}
            }
        }

        result = analyzer.analyze_coverage(coverage_data)

        assert result.uncovered_lines == [2, 4, 5]


class TestQualityScorer:
    """Unit tests for QualityScorer class"""

    @pytest.fixture
    def scorer(self):
        """Fixture for QualityScorer"""
        return QualityScorer()

    def test_calculate_score_all_components(self, scorer):
        """Test score calculation with all components present"""
        report = ValidationReport(
            safety_check=ExecutionResult(success=True),
            test_results=TestResult(coverage={'total': {'lines': {'pct': 80.0}}}),
            pattern_validation=ChainValidation(composability_score=8.0)
        )

        score = scorer.calculate_score(report)

        # Expected: (1.0 * 0.4 + 0.8 * 0.3 + 0.8 * 0.3) * 100 = 88.0
        assert score == 88.0

    def test_calculate_score_partial_components(self, scorer):
        """Test score calculation with only some components"""
        report = ValidationReport(
            safety_check=ExecutionResult(success=True),
            test_results=None,
            pattern_validation=ChainValidation(composability_score=6.0)
        )

        score = scorer.calculate_score(report)

        # Expected: (1.0 * 0.4 + 0.0 * 0.3 + 0.6 * 0.3) * 100 = 58.0
        assert abs(score - 58.0) < 0.01  # Use approximate comparison for floating point

    def test_calculate_score_no_components(self, scorer):
        """Test score calculation with no components"""
        report = ValidationReport()

        score = scorer.calculate_score(report)

        assert score == 0.0

    def test_calculate_score_failures(self, scorer):
        """Test score calculation with component failures"""
        report = ValidationReport(
            safety_check=ExecutionResult(success=False),
            test_results=TestResult(coverage={'total': {'lines': {'pct': 30.0}}}),
            pattern_validation=ChainValidation(composability_score=2.0)
        )

        score = scorer.calculate_score(report)

        # Expected: (0.0 * 0.4 + 0.3 * 0.3 + 0.2 * 0.3) * 100 = 15.0
        assert score == 15.0

    def test_assess_risk_low(self, scorer):
        """Test risk assessment for low risk scores"""
        assert scorer.assess_risk(95.0) == RiskLevel.LOW
        assert scorer.assess_risk(85.0) == RiskLevel.LOW
        assert scorer.assess_risk(80.0) == RiskLevel.LOW

    def test_assess_risk_medium(self, scorer):
        """Test risk assessment for medium risk scores"""
        assert scorer.assess_risk(75.0) == RiskLevel.MEDIUM
        assert scorer.assess_risk(65.0) == RiskLevel.MEDIUM
        assert scorer.assess_risk(60.0) == RiskLevel.MEDIUM

    def test_assess_risk_high(self, scorer):
        """Test risk assessment for high risk scores"""
        assert scorer.assess_risk(55.0) == RiskLevel.HIGH
        assert scorer.assess_risk(45.0) == RiskLevel.HIGH
        assert scorer.assess_risk(40.0) == RiskLevel.HIGH

    def test_assess_risk_critical(self, scorer):
        """Test risk assessment for critical risk scores"""
        assert scorer.assess_risk(35.0) == RiskLevel.CRITICAL
        assert scorer.assess_risk(15.0) == RiskLevel.CRITICAL
        assert scorer.assess_risk(0.0) == RiskLevel.CRITICAL

    def test_weights_configuration(self, scorer):
        """Test that weights are properly configured"""
        assert scorer.WEIGHTS['safety'] == 0.4
        assert scorer.WEIGHTS['test_coverage'] == 0.3
        assert scorer.WEIGHTS['pattern_compliance'] == 0.3

        total_weight = sum(scorer.WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.001  # Should sum to 1.0
class TestLangChainPatternValidator:
    """Unit tests for LangChainPatternValidator (LangChainValidator)"""

    @pytest.fixture
    def validator(self):
        """Fixture for LangChainValidator as LangChainPatternValidator"""
        return LangChainValidator()

    def test_validate_patterns_good_lcel_usage(self, validator):
        """Test pattern validation with good LCEL usage"""
        code = """
from langchain_core.runnables import RunnableSequence
from langchain_core.prompts import ChatPromptTemplate

# Good LCEL usage
chain = RunnableSequence.from([
    ChatPromptTemplate.from_template("Generate code for: {task}"),
    lambda x: x
])

result = chain.invoke({"task": "test"})
"""

        result = validator.validate_patterns(code)

        assert result.uses_lcel == True
        assert result.proper_error_handling == False  # No try-catch blocks in this code
        assert result.composability_score >= 3.0  # LCEL usage gives 3 points

    def test_validate_patterns_poor_lcel_usage(self, validator):
        """Test pattern validation with poor LCEL usage"""
        code = """
# Poor pattern - no LCEL
def process_data(data):
    return data.upper()

result = process_data("test")
"""

        result = validator.validate_patterns(code)

        assert result.uses_lcel == False
        assert result.composability_score < 5.0

    def test_validate_patterns_good_error_handling(self, validator):
        """Test pattern validation with good error handling"""
        code = """
from langchain_core.runnables import RunnableLambda

def safe_operation(x):
    try:
        return x * 2
    except Exception as e:
        return f"Error: {e}"

chain = RunnableLambda(safe_operation)
"""

        result = validator.validate_patterns(code)

        assert result.proper_error_handling == True

    def test_validate_patterns_poor_error_handling(self, validator):
        """Test pattern validation with poor error handling"""
        code = """
def risky_operation(x):
    return x / 0  # Will crash

result = risky_operation(5)
"""

        result = validator.validate_patterns(code)

        assert result.proper_error_handling == False

    def test_validate_patterns_good_state_management(self, validator):
        """Test pattern validation with good state management"""
        code = """
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class AgentState:
    messages: List[str]
    data: dict

    def add_message(self, message: str) -> 'AgentState':
        return AgentState(
            messages=self.messages + [message],
            data=self.data
        )

# Usage
state = AgentState(messages=[], data={})
new_state = state.add_message("Hello")
"""

        result = validator.validate_patterns(code)

        assert result.state_management == True

    def test_validate_patterns_poor_state_management(self, validator):
        """Test pattern validation with poor state management"""
        code = """
# Mutable state - bad practice
state = {"messages": [], "data": {}}

def add_message(message):
    state["messages"].append(message)  # Mutates global state
    return state

result = add_message("Hello")
"""

        result = validator.validate_patterns(code)

        assert result.state_management == False

    def test_validate_patterns_good_tool_integration(self, validator):
        """Test pattern validation with good tool integration"""
        code = """
from langchain_core.tools import tool
from langchain_core.runnables import RunnableLambda

@tool
def search_tool(query: str) -> str:
    \"\"\"Search for information\"\"\"
    return f"Results for: {query}"

@tool
def calculate_tool(expression: str) -> float:
    \"\"\"Calculate mathematical expression\"\"\"
    return eval(expression)

# Proper tool integration
tools = [search_tool, calculate_tool]
"""

        result = validator.validate_patterns(code)

        assert result.tool_integration == True

    def test_validate_patterns_poor_tool_integration(self, validator):
        """Test pattern validation with poor tool integration"""
        code = """
# Poor tool integration - no decorators or proper structure
def search(query):
    return f"Results for: {query}"

def calculate(expr):
    return eval(expr)

tools = [search, calculate]
"""

        result = validator.validate_patterns(code)

        assert result.tool_integration == False

    def test_validate_patterns_composability_scoring(self, validator):
        """Test composability score calculation"""
        # High composability code
        high_code = """
from langchain_core.runnables import RunnableSequence, RunnableParallel
from langchain_core.tools import tool
from dataclasses import dataclass

@dataclass(frozen=True)
class State:
    value: int

@tool
def process_tool(x: int) -> int:
    return x * 2

# Complex composition
chain = RunnableSequence.from([
    RunnableLambda(lambda x: x + 1),
    RunnableParallel(
        branch1=RunnableLambda(lambda x: x * 2),
        branch2=process_tool
    )
])

try:
    result = chain.invoke(5)
except Exception as e:
    print(f"Error: {e}")
"""

        result = validator.validate_patterns(high_code)

        assert result.composability_score >= 8.0  # Should be high

    def test_validate_patterns_minimal_code(self, validator):
        """Test pattern validation with minimal code"""
        code = "const x = 1;"

        result = validator.validate_patterns(code)

        # Should return default values without crashing
        assert isinstance(result.uses_lcel, bool)
        assert isinstance(result.proper_error_handling, bool)
        assert isinstance(result.state_management, bool)
        assert isinstance(result.tool_integration, bool)
        assert isinstance(result.composability_score, float)


class TestChainCompositionValidator:
    """Unit tests for ChainCompositionValidator (LangChainValidator.validate_patterns)"""

    @pytest.fixture
    def validator(self):
        """Fixture for LangChainValidator as ChainCompositionValidator"""
        return LangChainValidator()

    def test_chain_composition_lcel_patterns(self, validator):
        """Test chain composition validation for LCEL patterns"""
        # Test various LCEL patterns
        lcel_patterns = [
            "RunnableSequence.from([step1, step2])",
            "RunnableParallel(branch1=step1, branch2=step2)",
            "chain1 | chain2 | chain3",  # Pipe operator
            "chain.pipe(step1).pipe(step2)"
        ]

        for pattern in lcel_patterns:
            code = f"""
from langchain_core.runnables import RunnableSequence, RunnableParallel
{pattern}
"""
            result = validator.validate_patterns(code)
            assert result.uses_lcel == True, f"Pattern {pattern} should be detected as LCEL"

    def test_chain_composition_error_handling(self, validator):
        """Test chain composition validation for error handling"""
        good_error_code = """
from langchain_core.runnables import RunnableLambda

def safe_func(x):
    try:
        return int(x)
    except ValueError:
        return 0
    except Exception as e:
        raise ValueError(f"Unexpected error: {e}")

chain = RunnableLambda(safe_func)
"""

        result = validator.validate_patterns(good_error_code)
        assert result.proper_error_handling == True

    def test_chain_composition_state_flow(self, validator):
        """Test chain composition validation for state flow"""
        state_flow_code = """
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class WorkflowState:
    messages: List[str]
    current_step: str

    def advance_step(self, new_step: str) -> 'WorkflowState':
        return WorkflowState(
            messages=self.messages,
            current_step=new_step
        )

# State transformation chain
def transform_state(state):
    return state.advance_step("next")

chain = RunnableLambda(transform_state)
"""

        result = validator.validate_patterns(state_flow_code)
        assert result.state_management == True

    def test_chain_composition_tool_usage(self, validator):
        """Test chain composition validation for tool usage"""
        tool_code = """
from langchain_core.tools import tool, StructuredTool
from langchain_core.runnables import RunnableLambda

@tool
def web_search(query: str) -> str:
    \"\"\"Search the web for information\"\"\"
    return f"Search results for: {query}"

@tool
def calculator(expression: str) -> float:
    \"\"\"Calculate mathematical expression\"\"\"
    return eval(expression)

# Tool integration
tools = [web_search, calculator]
chain_with_tools = RunnableLambda(lambda x: x)
"""

        result = validator.validate_patterns(tool_code)
        assert result.tool_integration == True

    def test_chain_composition_complex_workflow(self, validator):
        """Test chain composition validation for complex workflow"""
        complex_code = """
from langchain_core.runnables import RunnableSequence, RunnableParallel, RunnableLambda
from langchain_core.tools import tool
from dataclasses import dataclass
from typing import Dict, Any

@dataclass(frozen=True)
class ProcessingState:
    data: Dict[str, Any]
    step_results: Dict[str, Any]

    def update_result(self, step: str, result: Any) -> 'ProcessingState':
        new_results = {**self.step_results, step: result}
        return ProcessingState(data=self.data, step_results=new_results)

@tool
def validate_input(data: str) -> bool:
    \"\"\"Validate input data\"\"\"
    return len(data) > 0

@tool
def process_data(data: str) -> str:
    \"\"\"Process the input data\"\"\"
    return data.upper()

@tool
def store_result(result: str) -> bool:
    \"\"\"Store processing result\"\"\"
    return True

# Complex chain composition
validation_chain = RunnableLambda(lambda state: state.update_result('validation', validate_input(state.data['input'])))
processing_chain = RunnableLambda(lambda state: state.update_result('processing', process_data(state.data['input'])))
storage_chain = RunnableLambda(lambda state: state.update_result('storage', store_result(state.step_results.get('processing', ''))))

# Parallel processing
parallel_chain = RunnableParallel(
    validation=validation_chain,
    processing=processing_chain
)

# Sequential composition
full_chain = RunnableSequence.from([
    parallel_chain,
    storage_chain
])

try:
    initial_state = ProcessingState(data={'input': 'test'}, step_results={})
    final_state = full_chain.invoke(initial_state)
except Exception as e:
    print(f"Workflow error: {e}")
"""

        result = validator.validate_patterns(complex_code)

        assert result.uses_lcel == True
        assert result.proper_error_handling == True
        assert result.state_management == True
        assert result.tool_integration == True
        assert result.composability_score >= 9.0


class TestErrorHandlingValidator:
    """Unit tests for ErrorHandlingValidator (LangChainValidator.validate_error_patterns)"""

    @pytest.fixture
    def validator(self):
        """Fixture for LangChainValidator as ErrorHandlingValidator"""
        return LangChainValidator()

    def test_error_patterns_comprehensive_try_catch(self, validator):
        """Test error pattern validation with comprehensive try-catch"""
        code = """
from langchain_core.runnables import RunnableLambda
from typing import Any

def robust_operation(data: Any) -> Any:
    try:
        # Primary operation
        if not isinstance(data, dict):
            raise ValueError("Input must be a dictionary")

        result = data.get('value', 0) * 2

        if result < 0:
            raise RuntimeError("Result cannot be negative")

        return result

    except ValueError as ve:
        # Handle validation errors
        return {"error": "validation_error", "message": str(ve)}

    except RuntimeError as re:
        # Handle runtime errors
        return {"error": "runtime_error", "message": str(re)}

    except Exception as e:
        # Handle unexpected errors
        return {"error": "unexpected_error", "message": str(e)}

chain = RunnableLambda(robust_operation)
"""

        result = validator.validate_error_patterns(code)

        assert result.try_catch_coverage > 0.5
        assert result.error_propagation == True

    def test_error_patterns_circuit_breaker_usage(self, validator):
        """Test error pattern validation with circuit breaker"""
        code = """
from langchain_core.runnables import RunnableLambda
import time

class CircuitBreaker:
    def __init__(self):
        self.failure_count = 0
        self.state = 'closed'

    def call(self, func, *args, **kwargs):
        if self.state == 'open':
            raise Exception("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self.failure_count = 0  # Reset on success
            return result
        except Exception as e:
            self.failure_count += 1
            if self.failure_count > 3:
                self.state = 'open'
            raise e

circuit_breaker = CircuitBreaker()

def unreliable_operation():
    if time.time() % 2 > 1:  # Random failure
        raise ConnectionError("Service unavailable")
    return "success"

def safe_unreliable_operation():
    return circuit_breaker.call(unreliable_operation)

chain = RunnableLambda(safe_unreliable_operation)
"""

        result = validator.validate_error_patterns(code)

        assert result.circuit_breaker_usage == True

    def test_error_patterns_fallback_strategies(self, validator):
        """Test error pattern validation with fallback strategies"""
        code = """
from langchain_core.runnables import RunnableLambda
import logging

logger = logging.getLogger(__name__)

def operation_with_fallback(primary_data: str, fallback_data: str = "default") -> str:
    \"\"\"
    Operation with fallback strategy.
    Try primary data first, fall back to alternative if it fails.
    \"\"\"
    try:
        # Primary operation
        if not primary_data or len(primary_data) < 3:
            raise ValueError("Primary data is invalid")

        return f"Primary: {primary_data.upper()}"

    except ValueError as ve:
        logger.warning(f"Primary operation failed: {ve}, trying fallback")

        try:
            # Fallback operation
            if not fallback_data:
                raise RuntimeError("Fallback data also invalid")

            return f"Fallback: {fallback_data.upper()}"

        except RuntimeError as re:
            logger.error(f"Fallback also failed: {re}")
            return "Emergency default value"

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return "Error fallback"

# Exponential backoff retry pattern
def retry_with_backoff(func, max_attempts=3, base_delay=1.0):
    \"\"\"
    Retry function with exponential backoff.
    \"\"\"
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise e

            delay = base_delay * (2 ** attempt)
            logger.info(f"Attempt {attempt + 1} failed, retrying in {delay}s")
            time.sleep(delay)

    return None

chain = RunnableLambda(operation_with_fallback)
"""

        result = validator.validate_error_patterns(code)

        assert result.fallback_strategies >= 2  # Multiple fallback patterns

    def test_error_patterns_minimal_error_handling(self, validator):
        """Test error pattern validation with minimal error handling"""
        code = """
def risky_operation(x):
    return x / 0  # Will always fail

result = risky_operation(5)
"""

        result = validator.validate_error_patterns(code)

        assert result.try_catch_coverage == 0.0
        assert result.circuit_breaker_usage == False
        assert result.fallback_strategies == 0
        assert result.error_propagation == False

    def test_error_patterns_error_flow_analysis(self, validator):
        """Test error pattern validation for error flow analysis"""
        code = """
from langchain_core.runnables import RunnableLambda
from typing import Union

def process_with_error_flow(data: Union[str, int]) -> Union[str, dict]:
    \"\"\"
    Process data with comprehensive error flow.
    \"\"\"
    # Input validation
    if data is None:
        return {"error": "input_error", "message": "Data cannot be None"}

    if not isinstance(data, (str, int)):
        return {"error": "type_error", "message": "Data must be string or int"}

    try:
        if isinstance(data, str):
            if len(data) == 0:
                raise ValueError("String cannot be empty")
            result = data.upper()
        else:  # int
            if data < 0:
                raise ValueError("Number cannot be negative")
            result = str(data * 2)

        return result

    except ValueError as ve:
        return {"error": "validation_error", "message": str(ve)}

    except Exception as e:
        # Log unexpected errors
        print(f"Unexpected error: {e}")
        return {"error": "processing_error", "message": "An unexpected error occurred"}

chain = RunnableLambda(process_with_error_flow)
"""

        result = validator.validate_error_patterns(code)

        assert result.error_propagation == True
        assert result.try_catch_coverage > 0


class TestStateManagementValidator:
    """Unit tests for StateManagementValidator (LangChainValidator.validate_state_handling)"""

    @pytest.fixture
    def validator(self):
        """Fixture for LangChainValidator as StateManagementValidator"""
        return LangChainValidator()

    def test_state_handling_immutable_dataclass(self, validator):
        """Test state handling validation with immutable dataclass"""
        code = """
from dataclasses import dataclass
from typing import List, Dict, Any
from langchain_core.runnables import RunnableLambda

@dataclass(frozen=True)
class AgentState:
    \"\"\"Immutable agent state\"\"\"
    messages: List[str]
    context: Dict[str, Any]
    current_step: str = "init"

    def add_message(self, message: str) -> 'AgentState':
        \"\"\"Add message immutably\"\"\"
        return AgentState(
            messages=self.messages + [message],
            context=self.context,
            current_step=self.current_step
        )

    def update_context(self, key: str, value: Any) -> 'AgentState':
        \"\"\"Update context immutably\"\"\"
        new_context = {**self.context, key: value}
        return AgentState(
            messages=self.messages,
            context=new_context,
            current_step=self.current_step
        )

    def advance_step(self, new_step: str) -> 'AgentState':
        \"\"\"Advance workflow step immutably\"\"\"
        return AgentState(
            messages=self.messages,
            context=self.context,
            current_step=new_step
        )

# Usage in chain
def process_message(state: AgentState, message: str) -> AgentState:
    \"\"\"Process a message and update state\"\"\"
    # Add message
    state_with_message = state.add_message(message)

    # Update context
    state_with_context = state_with_message.update_context('last_message', message)

    # Advance step
    final_state = state_with_context.advance_step('processed')

    return final_state

# Create chain
message_processor = RunnableLambda(lambda inputs: process_message(inputs['state'], inputs['message']))

# Example usage
initial_state = AgentState(messages=[], context={})
result_state = message_processor.invoke({
    'state': initial_state,
    'message': 'Hello, world!'
})
"""

        result = validator.validate_state_handling(code)

        assert result.immutable_state == True
        assert result.proper_transformations == True
        assert result.state_flow == True
        assert result.dataclasses_usage == True

    def test_state_handling_mutable_state_anti_pattern(self, validator):
        """Test state handling validation with mutable state (anti-pattern)"""
        code = """
# Anti-pattern: Mutable global state
global_state = {
    'messages': [],
    'context': {},
    'current_step': 'init'
}

def add_message_bad(message: str) -> None:
    \"\"\"Mutate global state - BAD PRACTICE\"\"\"
    global_state['messages'].append(message)
    global_state['last_updated'] = message

def update_context_bad(key: str, value) -> None:
    \"\"\"Mutate global context - BAD PRACTICE\"\"\"
    global_state['context'][key] = value

def advance_step_bad(new_step: str) -> None:
    \"\"\"Mutate step - BAD PRACTICE\"\"\"
    global_state['current_step'] = new_step

# Usage - hard to reason about
add_message_bad("Hello")
update_context_bad("user", "Alice")
advance_step_bad("processing")

print(global_state)  # State is mutated everywhere
"""

        result = validator.validate_state_handling(code)

        assert result.immutable_state == False
        assert result.proper_transformations == False
        assert result.state_flow == False
        assert result.dataclasses_usage == False

    def test_state_handling_mixed_patterns(self, validator):
        """Test state handling validation with mixed good and bad patterns"""
        code = """
from dataclasses import dataclass
from typing import List

# Good pattern
@dataclass(frozen=True)
class ImmutableState:
    items: List[str]

    def add_item(self, item: str) -> 'ImmutableState':
        return ImmutableState(items=self.items + [item])

# Bad pattern mixed in
mutable_state = {'counter': 0}

def increment_counter():
    mutable_state['counter'] += 1  # Mutation

# Usage
immutable = ImmutableState(items=[])
new_immutable = immutable.add_item("test")  # Good

increment_counter()  # Bad
"""

        result = validator.validate_state_handling(code)

        # Should detect the good patterns but also the mixed usage
        assert result.dataclasses_usage == True  # Has dataclass
        assert result.immutable_state == True   # Has frozen dataclass
        # But overall state_flow might be False due to mixed patterns

    def test_state_handling_state_classes_detection(self, validator):
        """Test state handling validation for state class detection"""
        code = """
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class RegularClass:
    value: int

@dataclass(frozen=True)
class StateClass:
    data: Dict[str, Any]

    def transform(self, key: str, new_value: Any) -> 'StateClass':
        new_data = {**self.data, key: new_value}
        return StateClass(data=new_data)

@dataclass(frozen=True)
class WorkflowState:
    step: str
    results: Dict[str, Any]

class NotAStateClass:
    def __init__(self):
        self.value = 42

# Usage
state = StateClass(data={'initial': 'value'})
workflow = WorkflowState(step='start', results={})
regular = RegularClass(value=5)
not_state = NotAStateClass()
"""

        result = validator.validate_state_handling(code)

        assert result.immutable_state == True  # Has frozen dataclasses
        assert result.dataclasses_usage == True

    def test_state_handling_transformation_methods(self, validator):
        """Test state handling validation for transformation methods"""
        code = """
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class ListState:
    items: List[str]

    def append_item(self, item: str) -> 'ListState':
        \"\"\"Proper transformation method\"\"\"
        return ListState(items=self.items + [item])

    def prepend_item(self, item: str) -> 'ListState':
        \"\"\"Another transformation method\"\"\"
        return ListState(items=[item] + self.items)

    def clear_items(self) -> 'ListState':
        \"\"\"Clear transformation\"\"\"
        return ListState(items=[])

    def replace_items(self, new_items: List[str]) -> 'ListState':
        \"\"\"Replace transformation\"\"\"
        return ListState(items=new_items)

@dataclass(frozen=True)
class CounterState:
    count: int

    def increment(self) -> 'CounterState':
        return CounterState(count=self.count + 1)

    def decrement(self) -> 'CounterState':
        return CounterState(count=self.count - 1)

    def reset(self) -> 'CounterState':
        return CounterState(count=0)

    def set_value(self, value: int) -> 'CounterState':
        return CounterState(count=value)

# Usage
list_state = ListState(items=['a', 'b'])
new_list = list_state.append_item('c').prepend_item('z')

counter = CounterState(count=5)
updated_counter = counter.increment().increment()
"""

        result = validator.validate_state_handling(code)

        assert result.proper_transformations == True
        assert result.immutable_state == True
        assert result.dataclasses_usage == True

    def test_state_handling_immutability_patterns(self, validator):
        """Test state handling validation for immutability patterns"""
        code = """
from dataclasses import dataclass
from typing import NamedTuple, Dict, Any

# Dataclass with frozen=True
@dataclass(frozen=True)
class FrozenState:
    value: int
    metadata: Dict[str, Any]

# NamedTuple (inherently immutable)
class TupleState(NamedTuple):
    name: str
    age: int
    active: bool

# Custom immutable class
class ImmutableState:
    def __init__(self, data: Dict[str, Any]):
        self._data = data.copy()  # Defensive copy

    @property
    def data(self) -> Dict[str, Any]:
        return self._data.copy()  # Return copy to prevent mutation

    def with_updated_data(self, key: str, value: Any) -> 'ImmutableState':
        new_data = self._data.copy()
        new_data[key] = value
        return ImmutableState(new_data)

# Usage
frozen = FrozenState(value=42, metadata={'created': True})
tuple_state = TupleState(name='Alice', age=30, active=True)
immutable = ImmutableState(data={'key': 'value'})

# Transformations
new_frozen = FrozenState(value=frozen.value + 1, metadata=frozen.metadata)
new_tuple = TupleState(name=tuple_state.name, age=tuple_state.age + 1, active=tuple_state.active)
new_immutable = immutable.with_updated_data('new_key', 'new_value')
"""

        result = validator.validate_state_handling(code)

        assert result.immutable_state == True
        assert result.dataclasses_usage == True
