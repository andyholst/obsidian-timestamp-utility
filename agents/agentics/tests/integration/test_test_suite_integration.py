"""
Integration tests for the LLM Test Suite Validator

These tests validate the integration between the test suite validator and the code validator framework,
ensuring they work together to provide comprehensive validation of LLM-generated code and tests.
"""

import pytest
import json

from src.test_suite import (
    LLMTestSuiteValidator,
    TestSuiteValidationResult,
    TestSuiteRiskLevel,
    validate_llm_test_suite,
    generate_test_suite_report
)
from src.code_validator import validate_generated_code, ValidationReport


class TestTestSuiteIntegration:
    """Integration tests for test suite validator with code validator framework"""

    @pytest.fixture
    def test_suite_validator(self):
        """Fixture for test suite validator"""
        return LLMTestSuiteValidator()

    @pytest.fixture
    def sample_typescript_code(self):
        """Sample TypeScript code for testing"""
        return """
export class UserService {
    private users: Map<string, any> = new Map();

    async createUser(userData: { id: string; name: string; email: string }): Promise<void> {
        if (!userData.id || !userData.name || !userData.email) {
            throw new Error('Invalid user data');
        }
        this.users.set(userData.id, userData);
    }

    async getUser(id: string): Promise<any> {
        const user = this.users.get(id);
        if (!user) {
            throw new Error('User not found');
        }
        return user;
    }

    async getAllUsers(): Promise<any[]> {
        return Array.from(this.users.values());
    }
}
"""

    @pytest.fixture
    def sample_typescript_tests(self):
        """Sample TypeScript tests for testing"""
        return """
import { UserService } from './source';

describe('UserService', () => {
    let userService: UserService;

    beforeEach(() => {
        userService = new UserService();
    });

    describe('createUser', () => {
        it('should create a user successfully', async () => {
            const userData = {
                id: '1',
                name: 'John Doe',
                email: 'john@example.com'
            };

            await expect(userService.createUser(userData)).resolves.toBeUndefined();

            const user = await userService.getUser('1');
            expect(user).toEqual(userData);
        });

        it('should throw error for invalid user data', async () => {
            const invalidData = { id: '', name: '', email: '' };

            await expect(userService.createUser(invalidData)).rejects.toThrow('Invalid user data');
        });

        it('should throw error for missing required fields', async () => {
            const incompleteData = { id: '1', name: 'John' }; // missing email

            await expect(userService.createUser(incompleteData as any)).rejects.toThrow('Invalid user data');
        });
    });

    describe('getUser', () => {
        it('should return user if exists', async () => {
            const userData = {
                id: '1',
                name: 'John Doe',
                email: 'john@example.com'
            };

            await userService.createUser(userData);
            const user = await userService.getUser('1');

            expect(user).toEqual(userData);
        });

        it('should throw error if user does not exist', async () => {
            await expect(userService.getUser('nonexistent')).rejects.toThrow('User not found');
        });
    });

    describe('getAllUsers', () => {
        it('should return all users', async () => {
            const users = [
                { id: '1', name: 'John', email: 'john@test.com' },
                { id: '2', name: 'Jane', email: 'jane@test.com' }
            ];

            for (const user of users) {
                await userService.createUser(user);
            }

            const allUsers = await userService.getAllUsers();
            expect(allUsers).toHaveLength(2);
            expect(allUsers).toEqual(expect.arrayContaining(users));
        });

        it('should return empty array when no users exist', async () => {
            const allUsers = await userService.getAllUsers();
            expect(allUsers).toEqual([]);
        });
    });
});
"""

    @pytest.fixture
    def sample_langchain_code(self):
        """Sample LangChain-style Python code"""
        return """
from langchain_core.runnables import RunnableLambda, RunnableSequence
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any
from dataclasses import dataclass

@dataclass(frozen=True)
class ProcessingState:
    input_text: str
    processed_data: Dict[str, Any] = None

    def with_processed_data(self, data: Dict[str, Any]) -> 'ProcessingState':
        return ProcessingState(
            input_text=self.input_text,
            processed_data=data
        )

class TextProcessor:
    def __init__(self, llm):
        self.llm = llm
        self.processing_chain = self._build_chain()

    def _build_chain(self) -> RunnableSequence:
        preprocess = RunnableLambda(self._preprocess_text)
        process = RunnableLambda(self._process_with_llm)
        postprocess = RunnableLambda(self._postprocess_result)

        return preprocess | process | postprocess

    def _preprocess_text(self, state: ProcessingState) -> ProcessingState:
        try:
            cleaned_text = state.input_text.strip().lower()
            return state.with_processed_data({"cleaned_text": cleaned_text})
        except Exception as e:
            raise ValueError(f"Preprocessing failed: {str(e)}")

    def _process_with_llm(self, state: ProcessingState) -> ProcessingState:
        try:
            prompt = ChatPromptTemplate.from_template(
                "Process this text: {text}"
            )
            chain = prompt | self.llm
            result = chain.invoke({"text": state.processed_data["cleaned_text"]})
            return state.with_processed_data({
                **state.processed_data,
                "llm_result": result.content
            })
        except Exception as e:
            raise ValueError(f"LLM processing failed: {str(e)}")

    def _postprocess_result(self, state: ProcessingState) -> Dict[str, Any]:
        try:
            return {
                "original_text": state.input_text,
                "processed_text": state.processed_data.get("llm_result", ""),
                "metadata": {
                    "processing_steps": ["preprocess", "llm", "postprocess"],
                    "timestamp": "2024-01-01T00:00:00Z"
                }
            }
        except Exception as e:
            raise ValueError(f"Postprocessing failed: {str(e)}")

    async def process(self, input_text: str) -> Dict[str, Any]:
        initial_state = ProcessingState(input_text=input_text)
        return await self.processing_chain.ainvoke(initial_state)
"""

    def test_full_test_suite_validation_with_code_validator(self, test_suite_validator, sample_typescript_code, sample_typescript_tests):
        """Test complete integration between test suite and code validator"""
        # Act
        result = test_suite_validator.validate_test_suite(
            sample_typescript_code,
            sample_typescript_tests,
            context={"is_typescript": True},
            include_code_validator=True
        )

        # Assert
        assert isinstance(result, TestSuiteValidationResult)
        assert result.code_hash
        assert result.test_hash
        assert result.overall_score >= 0
        assert result.overall_score <= 100
        assert isinstance(result.risk_level, TestSuiteRiskLevel)

        # Check that execution metrics are populated
        assert isinstance(result.code_execution.execution_time, (int, float))
        assert isinstance(result.test_execution.execution_time, (int, float))

        # Check that relationship analysis is performed
        assert isinstance(result.test_code_relationship.test_coverage, (int, float))
        assert isinstance(result.test_code_relationship.assertion_quality, (int, float))

        # Check that LangChain compliance is evaluated
        assert isinstance(result.langchain_compliance.overall_compliance, (int, float))

    def test_test_suite_validation_without_code_validator(self, test_suite_validator, sample_typescript_code, sample_typescript_tests):
        """Test test suite validation without code validator integration"""
        # Act
        result = test_suite_validator.validate_test_suite(
            sample_typescript_code,
            sample_typescript_tests,
            context={"is_typescript": True},
            include_code_validator=False
        )

        # Assert
        assert isinstance(result, TestSuiteValidationResult)
        assert result.overall_score >= 0
        assert result.overall_score <= 100

    def test_langchain_code_validation(self, test_suite_validator, sample_langchain_code):
        """Test validation of LangChain-style Python code"""
        # Create mock tests for the LangChain code
        mock_tests = """
describe('TextProcessor', () => {
    it('should process text', () => {
        expect(true).toBe(true);
    });
});
"""

        # Act
        result = test_suite_validator.validate_test_suite(
            sample_langchain_code,
            mock_tests,
            context={"is_agentics_code": True},
            include_code_validator=True
        )

        # Assert
        assert isinstance(result, TestSuiteValidationResult)
        assert result.langchain_compliance.lcel_usage  # Should detect LCEL usage
        assert result.langchain_compliance.error_handling_score > 0
        assert result.langchain_compliance.state_management_score > 0

    def test_detailed_report_generation(self, test_suite_validator, sample_typescript_code, sample_typescript_tests):
        """Test detailed report generation"""
        # Arrange
        result = test_suite_validator.validate_test_suite(
            sample_typescript_code,
            sample_typescript_tests,
            include_code_validator=True
        )

        # Act
        report = test_suite_validator.generate_detailed_report(
            sample_typescript_code,
            sample_typescript_tests,
            result
        )

        # Assert
        assert isinstance(report, str)
        assert "# Comprehensive Test Suite Validation Report" in report
        assert "Overall Score:" in report
        assert "Risk Level:" in report
        assert "## Code Samples" in report

    def test_code_validator_integration_error_handling(self, test_suite_validator):
        """Test error handling when code validator fails"""
        # Use malformed code that will cause validation errors
        malformed_code = "export class { invalid syntax }"
        malformed_tests = "describe('test') { it('fails') { expect().toBe() } }"

        # Act
        result = test_suite_validator.validate_test_suite(
            malformed_code,
            malformed_tests,
            include_code_validator=True
        )

        # Assert
        assert result.overall_score >= 0  # Should still calculate score
        assert len(result.critical_issues) > 0

    def test_empty_code_handling(self, test_suite_validator):
        """Test handling of empty code and tests"""
        # Act
        result = test_suite_validator.validate_test_suite("", "", include_code_validator=False)

        # Assert
        assert isinstance(result, TestSuiteValidationResult)
        assert result.overall_score == 0.0
        assert result.risk_level == TestSuiteRiskLevel.CRITICAL

    def test_malformed_code_handling(self, test_suite_validator):
        """Test handling of malformed code"""
        malformed_code = "export class { invalid syntax }"
        malformed_tests = "describe('test') { it('fails') { expect().toBe() } }"

        # Act
        result = test_suite_validator.validate_test_suite(
            malformed_code,
            malformed_tests,
            include_code_validator=False
        )

        # Assert
        assert isinstance(result, TestSuiteValidationResult)
        assert result.code_execution.success == False or result.test_execution.failed_tests > 0

    def test_global_functions(self, sample_typescript_code, sample_typescript_tests):
        """Test global convenience functions"""
        # Act
        result = validate_llm_test_suite(sample_typescript_code, sample_typescript_tests)
        report = generate_test_suite_report(sample_typescript_code, sample_typescript_tests, result)

        # Assert
        assert isinstance(result, TestSuiteValidationResult)
        assert isinstance(report, str)
        assert len(report) > 0

    def test_risk_level_assessment(self, test_suite_validator):
        """Test risk level assessment based on scores"""
        test_cases = [
            (85, TestSuiteRiskLevel.LOW),
            (75, TestSuiteRiskLevel.MEDIUM),
            (55, TestSuiteRiskLevel.HIGH),
            (25, TestSuiteRiskLevel.CRITICAL)
        ]

        for score, expected_risk in test_cases:
            # Create a mock result with specific score
            result = TestSuiteValidationResult()
            result.overall_score = score

            # Assess risk
            risk = test_suite_validator._assess_risk_level(score)

            assert risk == expected_risk, f"Score {score} should be {expected_risk.value}, got {risk.value}"

    def test_comprehensive_validation_workflow(self, test_suite_validator, sample_typescript_code, sample_typescript_tests):
        """Test the complete validation workflow end-to-end"""
        # Act
        result = validate_llm_test_suite(
            sample_typescript_code,
            sample_typescript_tests,
            context={
                "project_type": "typescript",
                "test_framework": "jest",
                "validation_level": "comprehensive"
            }
        )

        # Assert - comprehensive checks
        assert result.timestamp
        assert result.code_hash
        assert result.test_hash

        # Execution results should be populated
        assert hasattr(result.code_execution, 'success')
        assert hasattr(result.test_execution, 'total_tests')

        # Relationship analysis should be performed
        assert hasattr(result.test_code_relationship, 'test_coverage')
        assert hasattr(result.test_code_relationship, 'assertion_quality')

        # LangChain compliance should be evaluated
        assert hasattr(result.langchain_compliance, 'overall_compliance')

        # Recommendations should be generated
        assert isinstance(result.critical_issues, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.suggestions, list)

        # Overall score and risk should be calculated
        assert 0 <= result.overall_score <= 100
        assert isinstance(result.risk_level, TestSuiteRiskLevel)

    def test_executor_error_handling(self, test_suite_validator):
        """Test error handling when executor fails"""
        # Use malformed code that will cause execution errors
        malformed_code = "export class { invalid syntax }"
        malformed_tests = "describe('test') { it('fails') { expect().toBe() } }"

        # Act
        result = test_suite_validator.validate_test_suite(malformed_code, malformed_tests)

        # Assert
        assert result.overall_score >= 0.0
        assert len(result.critical_issues) > 0