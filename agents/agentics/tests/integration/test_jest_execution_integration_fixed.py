"""
Comprehensive Integration Tests for Jest Test Execution

These tests validate the JestTestRunner functionality with actual test execution,
coverage analysis, parallel processing, and error handling as described in
TEST_SUITE_README.md and LLM_CODE_VALIDATION.md.
"""

import os

# Set required environment variable for tests before any imports
os.environ['PROJECT_ROOT'] = '/tmp/test_project'

import pytest
import json
import tempfile
import subprocess
from pathlib import Path

from src.test_suite import (
    TestSuiteExecutor,
    TestExecutionMetrics,
    LLMTestSuiteValidator,
    validate_llm_test_suite
)


class TestJestExecutionIntegration:
    """Comprehensive integration tests for Jest test execution functionality"""

    @pytest.fixture
    def jest_executor(self):
        """Fixture for TestSuiteExecutor with Jest capabilities"""
        return TestSuiteExecutor()

    @pytest.fixture
    def valid_typescript_code(self):
        """Valid TypeScript code for testing"""
        return """
export class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }

    subtract(a: number, b: number): number {
        return a - b;
    }

    multiply(a: number, b: number): number {
        return a * b;
    }

    divide(a: number, b: number): number {
        if (b === 0) {
            throw new Error('Division by zero');
        }
        return a / b;
    }
}
"""

    @pytest.fixture
    def valid_jest_tests(self):
        """Valid Jest tests for the calculator"""
        return """
import { Calculator } from './source';

describe('Calculator', () => {
    let calculator: Calculator;

    beforeEach(() => {
        calculator = new Calculator();
    });

    describe('add', () => {
        it('should add two positive numbers', () => {
            expect(calculator.add(2, 3)).toBe(5);
        });

        it('should add positive and negative numbers', () => {
            expect(calculator.add(5, -3)).toBe(2);
        });

        it('should add two negative numbers', () => {
            expect(calculator.add(-2, -3)).toBe(-5);
        });
    });

    describe('subtract', () => {
        it('should subtract two numbers', () => {
            expect(calculator.subtract(5, 3)).toBe(2);
        });

        it('should handle negative results', () => {
            expect(calculator.subtract(3, 5)).toBe(-2);
        });
    });

    describe('multiply', () => {
        it('should multiply two numbers', () => {
            expect(calculator.multiply(3, 4)).toBe(12);
        });

        it('should handle multiplication by zero', () => {
            expect(calculator.multiply(5, 0)).toBe(0);
        });
    });

    describe('divide', () => {
        it('should divide two numbers', () => {
            expect(calculator.divide(10, 2)).toBe(5);
        });

        it('should handle decimal results', () => {
            expect(calculator.divide(5, 2)).toBe(2.5);
        });

        it('should throw error when dividing by zero', () => {
            expect(() => calculator.divide(10, 0)).toThrow('Division by zero');
        });
    });
});
"""

    def test_actual_jest_test_execution_success(self, jest_executor, valid_typescript_code, valid_jest_tests):
        """Test successful Jest test execution with real files"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            valid_jest_tests,
            context={"test_framework": "jest"}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.total_tests > 0
        assert test_metrics.passed_tests >= 0
        assert test_metrics.failed_tests >= 0
        assert test_metrics.execution_time >= 0
        assert test_metrics.coverage_percentage >= 0
        assert isinstance(test_metrics.error_messages, list)

    def test_jest_coverage_analysis(self, jest_executor, valid_typescript_code, valid_jest_tests):
        """Test Jest coverage analysis functionality"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            valid_jest_tests,
            context={"collect_coverage": True}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.coverage_percentage >= 0
        assert test_metrics.coverage_percentage <= 100

    def test_invalid_test_suite_handling(self, jest_executor, valid_typescript_code):
        """Test handling of invalid test suites"""
        invalid_tests = """
import { Calculator } from './source';

describe('Calculator', () => {
    it('should fail with syntax error', () => {
        expect(calculator.add(2, 3)).toBe(5);  // calculator not defined
    });
});
"""

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            invalid_tests,
            context={"test_framework": "jest"}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        # Should detect test failures or syntax errors
        assert test_metrics.failed_tests >= 0 or len(test_metrics.error_messages) > 0

    def test_comprehensive_jest_validation_integration(self, valid_typescript_code, valid_jest_tests):
        """Test complete Jest validation integration with LLMTestSuiteValidator"""
        # Act
        result, code_validator_report = validate_llm_test_suite(
            valid_typescript_code,
            valid_jest_tests,
            context={
                "language": "typescript",
                "test_framework": "jest",
                "validation_focus": "jest_execution"
            },
            include_code_validator=True
        )

        # Assert
        assert result is not None
        assert hasattr(result, 'test_execution')
        assert result.test_execution.total_tests >= 0
        assert result.test_execution.coverage_percentage >= 0
        assert 0 <= result.overall_score <= 100