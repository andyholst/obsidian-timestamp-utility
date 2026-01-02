"""
Unit tests for individual components of the LLM Test Suite Validator

These tests focus on testing individual classes and methods in isolation.
"""

import pytest
import json
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

from src.test_suite import (
    TestSuiteExecutor,
    TestSuiteValidator,
    LangChainBestPracticesValidator,
    TestSuiteReporter,
    LLMTestSuiteValidator,
    SuiteValidationResult as TestSuiteValidationResult,
    SuiteRiskLevel as TestSuiteRiskLevel,
    TestExecutionMetrics,
    CodeExecutionMetrics,
    TestCodeRelationship,
    LangChainCompliance
)


class TestTestSuiteExecutor:
    """Unit tests for TestSuiteExecutor"""

    @pytest.fixture
    def executor(self):
        """Fixture for TestSuiteExecutor"""
        return TestSuiteExecutor()

    def test_executor_initialization(self, executor):
        """Test executor initialization"""
        assert executor.execution_timeout == 30000
        assert executor.memory_limit == "256MB"

    def test_extract_exports_class(self, executor):
        """Test export extraction for classes"""
        code = """
export class UserService {}
export function helper() {}
export const config = {};
"""
        exports = executor._extract_exports(code)
        assert "UserService" in exports
        assert "helper" in exports

    def test_extract_exports_empty(self, executor):
        """Test export extraction for code with no exports"""
        code = "console.log('hello');"
        exports = executor._extract_exports(code)
        assert exports == "*"

    def test_generate_smoke_test_with_class(self, executor):
        """Test smoke test generation for class exports"""
        code = "export class TestClass {}"
        smoke_test = executor._generate_smoke_test(code)
        assert "new TestClass()" in smoke_test

    def test_generate_smoke_test_with_function(self, executor):
        """Test smoke test generation for function exports"""
        code = "export function testFunc() {}"
        smoke_test = executor._generate_smoke_test(code)
        assert "testFunc()" in smoke_test

    @patch('src.test_suite.subprocess.run')
    def test_execute_generated_code_success(self, mock_run, executor):
        """Test successful code execution"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Code executed successfully",
            stderr=""
        )

        result = executor._execute_generated_code("export class Test {}", {})

        assert result.success == True
        assert result.execution_time >= 0
        assert result.error_count == 0

    @patch('src.test_suite.subprocess.run')
    def test_execute_generated_code_failure(self, mock_run, executor):
        """Test failed code execution"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Syntax error"
        )

        result = executor._execute_generated_code("invalid code", {})

        assert result.success == False
        assert result.error_count == 1

    @patch('src.test_suite.subprocess.run')
    def test_execute_generated_code_timeout(self, mock_run, executor):
        """Test code execution timeout"""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired(cmd=['npx', 'ts-node'], timeout=30)

        result = executor._execute_generated_code("export class Test {}", {})

        assert result.success == False
        assert result.timeout_occurred == True

    def test_parse_jest_results_success(self, executor):
        """Test parsing successful Jest results"""
        stdout = '{"testResults": [{"assertionResults": [{"status": "passed"}, {"status": "failed"}]}]}'
        stderr = ""
        temp_dir = "/tmp"

        result = executor._parse_jest_results(stdout, stderr, temp_dir)

        assert result['total'] == 2
        assert result['passed'] == 1
        assert result['failed'] == 1

    def test_parse_jest_results_fallback(self, executor):
        """Test fallback parsing when JSON fails"""
        stdout = "Tests: 3 passed, 1 failed"
        stderr = ""
        temp_dir = "/tmp"

        result = executor._parse_jest_results(stdout, stderr, temp_dir)

        assert result['passed'] == 3
        assert result['failed'] == 1
        assert result['total'] == 4


class TestTestSuiteValidator:
    """Unit tests for TestSuiteValidator"""

    @pytest.fixture
    def validator(self):
        """Fixture for TestSuiteValidator"""
        return TestSuiteValidator()

    def test_analyze_assertion_quality_high(self, validator):
        """Test assertion quality analysis with diverse assertions"""
        test_code = """
expect(result).toBe(true);
expect(result).toEqual(expected);
expect(mock).toHaveBeenCalled();
expect(func).toThrow();
expect(value).toBeDefined();
"""

        quality = validator._analyze_assertion_quality(test_code)
        assert quality > 5.0  # Should be high due to diversity

    def test_analyze_assertion_quality_low(self, validator):
        """Test assertion quality analysis with few assertions"""
        test_code = "expect(true).toBe(true);"

        quality = validator._analyze_assertion_quality(test_code)
        assert quality < 5.0  # Should be low

    def test_detect_mock_usage_jest(self, validator):
        """Test mock detection for Jest mocks"""
        test_code = "jest.mock('module'); jest.fn();"
        assert validator._detect_mock_usage(test_code) == True

    def test_detect_mock_usage_none(self, validator):
        """Test mock detection when no mocks present"""
        test_code = "expect(true).toBe(true);"
        assert validator._detect_mock_usage(test_code) == False

    def test_count_edge_cases(self, validator):
        """Test edge case counting"""
        test_code = """
it('should handle null input', () => {});
it('should handle empty string', () => {});
it('should handle max value', () => {});
it('should handle error case', () => {});
"""

        edge_cases = validator._count_edge_cases(test_code)
        assert edge_cases >= 4  # null, empty, max, error

    def test_categorize_tests_unit(self, validator):
        """Test test categorization for unit tests"""
        test_code = "describe('Unit Test', () => { it('works', () => {}); });"

        categories = validator._categorize_tests(test_code)
        assert categories['unit'] == 1
        assert categories['integration'] == 0

    def test_categorize_tests_integration(self, validator):
        """Test test categorization for integration tests"""
        test_code = "describe('Integration Test', () => { it('works', () => {}); });"

        categories = validator._categorize_tests(test_code)
        assert categories['integration'] == 1
        assert categories['unit'] == 1  # Also counts as unit


class TestLangChainBestPracticesValidator:
    """Unit tests for LangChainBestPracticesValidator"""

    @pytest.fixture
    def validator(self):
        """Fixture for LangChainBestPracticesValidator"""
        return LangChainBestPracticesValidator()

    def test_check_lcel_usage_positive(self, validator):
        """Test LCEL usage detection"""
        code = "const chain = RunnableSequence.from([step1, step2]); result | chain;"
        assert validator._check_lcel_usage(code) == True

    def test_check_lcel_usage_negative(self, validator):
        """Test LCEL usage not detected"""
        code = "const result = process(data);"
        assert validator._check_lcel_usage(code) == False

    def test_analyze_error_handling_comprehensive(self, validator):
        """Test comprehensive error handling analysis"""
        code = """
try {
    riskyOperation();
} catch (error) {
    handleError(error);
}
"""

        score = validator._analyze_error_handling(code)
        assert score > 5.0  # Should be decent

    def test_analyze_error_handling_minimal(self, validator):
        """Test minimal error handling analysis"""
        code = "const result = operation();"
        score = validator._analyze_error_handling(code)
        assert score < 3.0  # Should be low

    def test_analyze_state_management_good(self, validator):
        """Test good state management analysis"""
        code = """
@dataclass(frozen=True)
class State:
    value: int

    def with_value(self, new_value: int) -> 'State':
        return State(value=new_value)
"""

        score = validator._analyze_state_management(code)
        assert score > 5.0

    def test_analyze_state_management_poor(self, validator):
        """Test poor state management analysis"""
        code = "let state = { value: 1 }; state.value = 2;"
        score = validator._analyze_state_management(code)
        assert score < 3.0

    def test_calculate_composability_high(self, validator):
        """Test high composability score"""
        code = """
class Processor:
    def process(self, data):
        return data

const chain = RunnableSequence.from([processor1, processor2]);
"""

        score = validator._calculate_composability(code)
        assert score > 5.0

    def test_analyze_tool_integration_good(self, validator):
        """Test good tool integration analysis"""
        code = """
@tool
def my_tool(input: str) -> str:
    return input.upper()

chain = llm | bind_tools([my_tool]);
"""

        score = validator._analyze_tool_integration(code)
        assert score >= 5.0

    def test_validate_langchain_compliance_full(self, validator):
        """Test full LangChain compliance validation"""
        code = """
from langchain_core.runnables import RunnableSequence
from langchain_core.tools import tool

@dataclass(frozen=True)
class State:
    data: str

    def transform(self, new_data: str) -> 'State':
        return State(data=new_data)

try:
    result = chain.invoke(input)
except Exception as e:
    handle_error(e)

@tool
def process_tool(input: str) -> str:
    return input
"""

        compliance = validator.validate_langchain_compliance(code)

        assert compliance.lcel_usage == True
        assert compliance.error_handling_score > 0
        assert compliance.state_management_score > 0
        assert compliance.tool_integration_score > 0
        assert compliance.overall_compliance > 5.0


class TestTestSuiteReporter:
    """Unit tests for TestSuiteReporter"""

    @pytest.fixture
    def reporter(self):
        """Fixture for TestSuiteReporter"""
        return TestSuiteReporter()

    @pytest.fixture
    def sample_result(self):
        """Sample validation result for testing"""
        return TestSuiteValidationResult(
            code_hash="abc123",
            test_hash="def456",
            overall_score=75.5,
            risk_level=TestSuiteRiskLevel.MEDIUM,
            critical_issues=["Issue 1"],
            warnings=["Warning 1"],
            suggestions=["Suggestion 1"]
        )

    def test_generate_header(self, reporter, sample_result):
        """Test header generation"""
        header = reporter._generate_header(sample_result)

        assert "Comprehensive Test Suite Validation Report" in header
        assert "75.5/100" in header
        assert "MEDIUM" in header

    def test_generate_execution_section(self, reporter, sample_result):
        """Test execution section generation"""
        section = reporter._generate_execution_section(sample_result)

        assert "## Execution Results" in section
        assert "Code Execution" in section
        assert "Test Execution" in section

    def test_generate_relationship_section(self, reporter, sample_result):
        """Test relationship section generation"""
        section = reporter._generate_relationship_section(sample_result)

        assert "## Test-Code Relationship Analysis" in section
        assert "Test Coverage:" in section

    def test_generate_compliance_section(self, reporter, sample_result):
        """Test compliance section generation"""
        section = reporter._generate_compliance_section(sample_result)

        assert "## LangChain Best Practices Compliance" in section
        assert "LCEL Usage:" in section

    def test_generate_recommendations_section(self, reporter, sample_result):
        """Test recommendations section generation"""
        section = reporter._generate_recommendations_section(sample_result)

        assert "## Recommendations" in section
        assert "### Critical Issues" in section
        assert "Issue 1" in section

    def test_generate_code_samples(self, reporter):
        """Test code samples generation"""
        code = "export class Test {}"
        tests = "describe('test', () => {});"

        section = reporter._generate_code_samples(code, tests)

        assert "## Code Samples" in section
        assert "```typescript" in section
        assert "export class Test {}" in section

    def test_generate_comprehensive_report(self, reporter, sample_result):
        """Test comprehensive report generation"""
        code = "export class Test {}"
        tests = "describe('test', () => {});"

        report = reporter.generate_comprehensive_report(code, tests, sample_result)

        assert isinstance(report, str)
        assert len(report) > 1000  # Should be comprehensive
        assert "Test Suite Validation Report" in report


class TestLLMTestSuiteValidator:
    """Unit tests for the main LLMTestSuiteValidator"""

    @pytest.fixture
    def validator(self):
        """Fixture for LLMTestSuiteValidator"""
        return LLMTestSuiteValidator()

    def test_initialization(self, validator):
        """Test validator initialization"""
        assert isinstance(validator.executor, TestSuiteExecutor)
        assert isinstance(validator.test_validator, TestSuiteValidator)
        assert isinstance(validator.langchain_validator, LangChainBestPracticesValidator)
        assert isinstance(validator.reporter, TestSuiteReporter)

    def test_generate_hash(self, validator):
        """Test hash generation"""
        content = "test content"
        hash1 = validator._generate_hash(content)
        hash2 = validator._generate_hash(content)

        assert hash1 == hash2  # Should be deterministic
        assert len(hash1) == 8  # Should be 8 characters

    def test_calculate_overall_score(self, validator):
        """Test overall score calculation"""
        result = TestSuiteValidationResult()

        # Mock the metrics
        result.code_execution.success = True
        result.test_execution.passed_tests = 8
        result.test_execution.total_tests = 10
        result.test_execution.coverage_percentage = 85.0
        result.test_code_relationship.test_coverage = 85.0
        result.test_code_relationship.assertion_quality = 7.0
        result.langchain_compliance.overall_compliance = 6.0

        score = validator._calculate_overall_score(result)

        assert 0 <= score <= 100
        assert score > 50  # Should be decent score

    def test_assess_risk_level(self, validator):
        """Test risk level assessment"""
        test_cases = [
            (90, TestSuiteRiskLevel.LOW),
            (70, TestSuiteRiskLevel.MEDIUM),
            (50, TestSuiteRiskLevel.HIGH),
            (20, TestSuiteRiskLevel.CRITICAL)
        ]

        for score, expected in test_cases:
            risk = validator._assess_risk_level(score)
            assert risk == expected

    @patch('src.test_suite.TestSuiteExecutor')
    def test_validate_test_suite_error_handling(self, mock_executor_class, validator):
        """Test error handling in validation"""
        mock_executor = MagicMock()
        mock_executor.execute_code_and_tests.side_effect = Exception("Test error")

        # Replace the executor
        validator.executor = mock_executor

        result, _ = validator.validate_test_suite("code", "tests")

        assert result.overall_score == 0.0
        assert result.risk_level == TestSuiteRiskLevel.CRITICAL
        assert len(result.critical_issues) > 0

    def test_generate_recommendations_comprehensive(self, validator):
        """Test comprehensive recommendations generation"""
        result = TestSuiteValidationResult()

        # Set up various failure conditions
        result.code_execution.success = False
        result.test_execution.failed_tests = 2
        result.test_execution.coverage_percentage = 30
        result.test_code_relationship.mock_usage = False
        result.test_code_relationship.edge_case_coverage = 1
        result.langchain_compliance.overall_compliance = 3.0

        validator._generate_recommendations(result)

        assert len(result.critical_issues) >= 2  # Code execution and test failures
        assert len(result.warnings) >= 2  # Coverage and edge cases
        assert len(result.suggestions) >= 1  # LangChain compliance


class TestDataClasses:
    """Unit tests for data classes and enums"""

    def test_test_suite_risk_level_enum(self):
        """Test risk level enum values"""
        assert TestSuiteRiskLevel.LOW.value == "low"
        assert TestSuiteRiskLevel.MEDIUM.value == "medium"
        assert TestSuiteRiskLevel.HIGH.value == "high"
        assert TestSuiteRiskLevel.CRITICAL.value == "critical"

    def test_test_suite_validation_result_initialization(self):
        """Test validation result initialization"""
        result = TestSuiteValidationResult()

        assert result.overall_score == 0.0
        assert result.risk_level == TestSuiteRiskLevel.LOW
        assert isinstance(result.critical_issues, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.suggestions, list)

    def test_test_execution_metrics(self):
        """Test test execution metrics"""
        metrics = TestExecutionMetrics(
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            execution_time=5.5,
            coverage_percentage=85.0
        )

        assert metrics.total_tests == 10
        assert metrics.passed_tests == 8
        assert metrics.failed_tests == 2
        assert metrics.execution_time == 5.5
        assert metrics.coverage_percentage == 85.0

    def test_code_execution_metrics(self):
        """Test code execution metrics"""
        metrics = CodeExecutionMetrics(
            success=True,
            execution_time=2.3,
            output_lines=5,
            error_count=0,
            timeout_occurred=False
        )

        assert metrics.success == True
        assert metrics.execution_time == 2.3
        assert metrics.output_lines == 5
        assert metrics.error_count == 0
        assert metrics.timeout_occurred == False

    def test_test_code_relationship(self):
        """Test test-code relationship metrics"""
        relationship = TestCodeRelationship(
            test_coverage=85.0,
            assertion_quality=7.5,
            mock_usage=True,
            edge_case_coverage=5,
            integration_test_count=2,
            unit_test_count=8
        )

        assert relationship.test_coverage == 85.0
        assert relationship.assertion_quality == 7.5
        assert relationship.mock_usage == True
        assert relationship.edge_case_coverage == 5
        assert relationship.integration_test_count == 2
        assert relationship.unit_test_count == 8

    def test_langchain_compliance(self):
        """Test LangChain compliance metrics"""
        compliance = LangChainCompliance(
            lcel_usage=True,
            error_handling_score=8.0,
            state_management_score=7.5,
            composability_score=9.0,
            tool_integration_score=6.5,
            overall_compliance=7.8
        )

        assert compliance.lcel_usage == True
        assert compliance.error_handling_score == 8.0
        assert compliance.state_management_score == 7.5
        assert compliance.composability_score == 9.0
        assert compliance.tool_integration_score == 6.5
        assert compliance.overall_compliance == 7.8

    def test_langchain_best_practices_validator_lcel_detection(self):
        """Test LCEL usage detection in code"""
        validator = LangChainBestPracticesValidator()

        # Test positive LCEL usage
        code_with_lcel = """
        const chain = RunnableSequence.from([step1, step2]);
        const result = await chain.invoke(input);
        """
        assert validator._check_lcel_usage(code_with_lcel) == True

        # Test negative LCEL usage
        code_without_lcel = """
        const result = processData(input);
        """
        assert validator._check_lcel_usage(code_without_lcel) == False

    def test_langchain_best_practices_validator_state_management(self):
        """Test state management pattern detection"""
        validator = LangChainBestPracticesValidator()

        # Test good state management
        good_state_code = """
        @dataclass(frozen=True)
        class AgentState:
            data: str

            def with_data(self, new_data: str) -> 'AgentState':
                return AgentState(data=new_data)
        """
        score = validator._analyze_state_management(good_state_code)
        assert score > 5.0

        # Test poor state management
        poor_state_code = "let state = { data: 'value' }; state.data = 'new';"
        score = validator._analyze_state_management(poor_state_code)
        assert score < 5.0

    def test_validation_result_markdown(self):
        """Test markdown report generation"""
        result = TestSuiteValidationResult(
            code_hash="abc123",
            test_hash="def456",
            overall_score=75.0,
            risk_level=TestSuiteRiskLevel.MEDIUM,
            critical_issues=["Critical issue"],
            warnings=["Warning"],
            suggestions=["Suggestion"]
        )

        markdown = result.to_markdown()

        assert "# Test Suite Validation Report" in markdown
        assert "75.0/100" in markdown
        assert "MEDIUM" in markdown
        assert "Critical issue" in markdown
        assert "Warning" in markdown
        assert "Suggestion" in markdown