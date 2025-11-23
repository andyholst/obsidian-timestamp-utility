"""
Minimal Integration Tests for Jest Test Execution

These tests provide basic validation of Jest test execution functionality
with real test execution and minimal coverage analysis.
"""

import pytest
import os
import tempfile
import subprocess
from pathlib import Path

from src.test_suite import TestSuiteExecutor, TestExecutionMetrics


class TestJestExecutionMinimal:
    """Minimal integration tests for Jest test execution functionality"""

    @pytest.fixture
    def jest_executor(self):
        """Fixture for TestSuiteExecutor with Jest capabilities"""
        return TestSuiteExecutor()

    @pytest.fixture
    def simple_typescript_code(self):
        """Simple TypeScript code for minimal testing"""
        return """
export class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }

    subtract(a: number, b: number): number {
        return a - b;
    }
}
"""

    @pytest.fixture
    def simple_jest_tests(self):
        """Simple Jest tests for the calculator"""
        return """
import { Calculator } from './source';

describe('Calculator', () => {
    let calculator: Calculator;

    beforeEach(() => {
        calculator = new Calculator();
    });

    describe('add', () => {
        it('should add two numbers', () => {
            expect(calculator.add(2, 3)).toBe(5);
        });
    });

    describe('subtract', () => {
        it('should subtract two numbers', () => {
            expect(calculator.subtract(5, 3)).toBe(2);
        });
    });
});
"""

    @pytest.mark.integration
    def test_basic_jest_test_execution(self, jest_executor, simple_typescript_code, simple_jest_tests):
        """Test basic Jest test execution with real files"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            simple_typescript_code,
            simple_jest_tests,
            context={"test_framework": "jest"}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.total_tests >= 0
        assert test_metrics.passed_tests >= 0
        assert test_metrics.failed_tests >= 0
        assert test_metrics.execution_time >= 0

    @pytest.mark.integration
    def test_jest_test_results_validation(self, jest_executor, simple_typescript_code, simple_jest_tests):
        """Test that Jest produces valid test results"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            simple_typescript_code,
            simple_jest_tests,
            context={"test_framework": "jest"}
        )

        # Assert
        assert test_metrics.total_tests == 2  # We have 2 test cases
        assert test_metrics.passed_tests == 2  # Both should pass
        assert test_metrics.failed_tests == 0  # None should fail
        assert test_metrics.execution_time > 0  # Should take some time to execute

    @pytest.mark.integration
    def test_jest_error_handling(self, jest_executor, simple_typescript_code):
        """Test Jest error handling with invalid tests"""
        invalid_tests = """
import { Calculator } from './source';

describe('Calculator', () => {
    it('should fail with invalid syntax', () => {
        expect(calculator.add(2, 3)).toBe(5);  // calculator not defined
    });
});
"""

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            simple_typescript_code,
            invalid_tests,
            context={"test_framework": "jest"}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        # Should detect the test failure
        assert test_metrics.failed_tests >= 1 or len(test_metrics.error_messages) > 0

    @pytest.mark.integration
    def test_jest_with_empty_tests(self, jest_executor, simple_typescript_code):
        """Test Jest execution with empty test suite"""
        empty_tests = """
describe('Empty Suite', () => {
    it('should pass', () => {
        expect(true).toBe(true);
    });
});
"""

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            simple_typescript_code,
            empty_tests,
            context={"test_framework": "jest"}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.total_tests >= 1  # At least the empty test

    @pytest.mark.integration
    def test_jest_execution_time_measurement(self, jest_executor, simple_typescript_code, simple_jest_tests):
        """Test that Jest execution time is properly measured"""
        import time

        start_time = time.time()

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            simple_typescript_code,
            simple_jest_tests,
            context={"test_framework": "jest"}
        )

        end_time = time.time()

        # Assert
        assert test_metrics.execution_time > 0
        assert test_metrics.execution_time <= (end_time - start_time + 1)  # Allow 1 second tolerance

    @pytest.mark.integration
    def test_jest_test_structure_recognition(self, jest_executor, simple_typescript_code, simple_jest_tests):
        """Test that Jest recognizes test structure correctly"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            simple_typescript_code,
            simple_jest_tests,
            context={"test_framework": "jest", "analyze_test_structure": True}
        )

        # Assert
        assert test_metrics.total_tests == 2
        # Should recognize describe blocks and test structure
        assert test_metrics.passed_tests + test_metrics.failed_tests == test_metrics.total_tests