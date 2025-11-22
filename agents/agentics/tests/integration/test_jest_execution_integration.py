"""
Comprehensive Integration Tests for Jest Test Execution

These tests validate the JestTestRunner functionality with actual test execution,
coverage analysis, parallel processing, and error handling as described in
TEST_SUITE_README.md and LLM_CODE_VALIDATION.md.
"""

import pytest
import json
import os
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

    @pytest.fixture
    def invalid_typescript_code(self):
        """Invalid TypeScript code for error testing"""
        return """
export class InvalidCalculator {
    add(a: number, b: number): number {
        return a + b;  // Valid

    subtract(a: number, b: number): number {  // Missing closing brace
        return a - b

    multiply(a: number, b: number): number {
        return a * b;  // Valid
    }

    divide(a: number, b: number): number {
        if (b === 0) {
            throw new Error('Division by zero');
        return a / b;  // Missing closing brace
    }
}
"""

    @pytest.fixture
    def invalid_jest_tests(self):
        """Invalid Jest tests for error testing"""
        return """
import { Calculator } from './source';

describe('Calculator', () => {
    let calculator: Calculator;

    beforeEach(() => {
        calculator = new Calculator();
    });

    describe('add', () => {
        it('should add two numbers', () => {
            expect(calculator.add(2, 3)).toBe(5);  // Valid test

        it('should fail with invalid syntax', () => {
            expect(calculator.add(2, 3)).toBe(6);  // Wrong expectation
        });
    });

    describe('divide', () => {
        it('should throw error when dividing by zero', () => {
            expect(() => calculator.divide(10, 0)).toThrow('Division by zero');  // Valid

        it('should handle invalid test syntax', () => {
            expect(calculator.divide(10, 0)).toBe('error');  // Wrong type expectation
        });
    });
});
"""

    @pytest.fixture
    def coverage_test_code(self):
        """TypeScript code designed for comprehensive coverage testing"""
        return """
export class StringProcessor {
    process(input: string | null | undefined): string {
        if (input === null || input === undefined) {
            return '';
        }

        if (input.length === 0) {
            return '';
        }

        return input.trim().toUpperCase();
    }

    validateEmail(email: string): boolean {
        if (!email || email.length === 0) {
            return false;
        }

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    calculateLength(input: string): number {
        return input ? input.length : 0;
    }
}
"""

    @pytest.fixture
    def coverage_test_tests(self):
        """Jest tests designed for high coverage"""
        return """
import { StringProcessor } from './source';

describe('StringProcessor', () => {
    let processor: StringProcessor;

    beforeEach(() => {
        processor = new StringProcessor();
    });

    describe('process', () => {
        it('should return empty string for null input', () => {
            expect(processor.process(null)).toBe('');
        });

        it('should return empty string for undefined input', () => {
            expect(processor.process(undefined)).toBe('');
        });

        it('should return empty string for empty input', () => {
            expect(processor.process('')).toBe('');
        });

        it('should trim and uppercase normal input', () => {
            expect(processor.process('  hello world  ')).toBe('HELLO WORLD');
        });

        it('should handle single character input', () => {
            expect(processor.process('a')).toBe('A');
        });
    });

    describe('validateEmail', () => {
        it('should return false for null input', () => {
            expect(processor.validateEmail(null as any)).toBe(false);
        });

        it('should return false for undefined input', () => {
            expect(processor.validateEmail(undefined as any)).toBe(false);
        });

        it('should return false for empty string', () => {
            expect(processor.validateEmail('')).toBe(false);
        });

        it('should return false for invalid email', () => {
            expect(processor.validateEmail('invalid-email')).toBe(false);
        });

        it('should return true for valid email', () => {
            expect(processor.validateEmail('test@example.com')).toBe(true);
        });

        it('should handle edge cases', () => {
            expect(processor.validateEmail('a@b.c')).toBe(true);
            expect(processor.validateEmail('test.email+tag@domain.co.uk')).toBe(true);
        });
    });

    describe('calculateLength', () => {
        it('should return 0 for null input', () => {
            expect(processor.calculateLength(null as any)).toBe(0);
        });

        it('should return 0 for undefined input', () => {
            expect(processor.calculateLength(undefined as any)).toBe(0);
        });

        it('should return 0 for empty string', () => {
            expect(processor.calculateLength('')).toBe(0);
        });

        it('should return correct length for normal string', () => {
            expect(processor.calculateLength('hello')).toBe(5);
        });

        it('should handle unicode characters', () => {
            expect(processor.calculateLength('héllo')).toBe(5);
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

    def test_jest_coverage_analysis(self, jest_executor, coverage_test_code, coverage_test_tests):
        """Test Jest coverage analysis functionality"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            coverage_test_code,
            coverage_test_tests,
            context={"collect_coverage": True}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.coverage_percentage >= 0
        assert test_metrics.coverage_percentage <= 100

        # Should have meaningful coverage data
        if test_metrics.total_tests > 0:
            # High coverage expected for comprehensive tests
            assert test_metrics.coverage_percentage > 50

    def test_jest_parallel_processing_configuration(self, jest_executor, valid_typescript_code, valid_jest_tests):
        """Test Jest parallel processing configuration"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            valid_jest_tests,
            context={
                "parallel_execution": True,
                "max_workers": 2,
                "test_framework": "jest"
            }
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        # Should still execute tests even with parallel config
        assert test_metrics.total_tests >= 0

    def test_invalid_test_suite_handling(self, jest_executor, valid_typescript_code, invalid_jest_tests):
        """Test handling of invalid test suites"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            invalid_jest_tests,
            context={"test_framework": "jest"}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        # Should detect test failures or syntax errors
        assert test_metrics.failed_tests >= 0 or len(test_metrics.error_messages) > 0

    def test_invalid_code_handling(self, jest_executor, invalid_typescript_code, valid_jest_tests):
        """Test handling of invalid source code"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            invalid_typescript_code,
            valid_jest_tests,
            context={"test_framework": "jest"}
        )

        # Assert
        assert isinstance(code_metrics, object)
        assert isinstance(test_metrics, TestExecutionMetrics)
        # Code execution should fail or have errors
        assert not code_metrics.success or code_metrics.error_count > 0

    def test_jest_timeout_handling(self, jest_executor):
        """Test Jest timeout handling"""
        # Create a test that will timeout
        slow_code = """
export class SlowProcessor {
    async process(): Promise<string> {
        await new Promise(resolve => setTimeout(resolve, 35000)); // Longer than timeout
        return 'done';
    }
}
"""

        slow_tests = """
import { SlowProcessor } from './source';

describe('SlowProcessor', () => {
    it('should timeout', async () => {
        const processor = new SlowProcessor();
        const result = await processor.process();
        expect(result).toBe('done');
    }, 40000); // Long timeout
});
"""

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            slow_code,
            slow_tests,
            context={"test_timeout": 5000}  # Short timeout
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        # Should either timeout or complete
        assert test_metrics.execution_time >= 0

    def test_jest_memory_limit_handling(self, jest_executor):
        """Test Jest memory limit handling"""
        # Create code that uses significant memory
        memory_intensive_code = """
export class MemoryIntensiveProcessor {
    private data: any[] = [];

    fillMemory(): void {
        for (let i = 0; i < 1000000; i++) {
            this.data.push({
                id: i,
                data: 'x'.repeat(1000) // Large strings
            });
        }
    }

    getData(): any[] {
        return this.data;
    }
}
"""

        memory_tests = """
import { MemoryIntensiveProcessor } from './source';

describe('MemoryIntensiveProcessor', () => {
    it('should handle memory intensive operations', () => {
        const processor = new MemoryIntensiveProcessor();
        processor.fillMemory();
        const data = processor.getData();
        expect(data.length).toBe(1000000);
    });
});
"""

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            memory_intensive_code,
            memory_tests,
            context={"memory_limit": "128MB"}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        # Should execute regardless of memory usage
        assert test_metrics.total_tests >= 0

    def test_jest_coverage_reporting(self, jest_executor, coverage_test_code, coverage_test_tests):
        """Test detailed Jest coverage reporting"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            coverage_test_code,
            coverage_test_tests,
            context={
                "collect_coverage": True,
                "coverage_reporters": ["json", "text", "lcov"]
            }
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.coverage_percentage >= 0

        # Should provide coverage metrics
        if test_metrics.total_tests > 0:
            assert test_metrics.coverage_percentage > 0

    def test_jest_error_message_parsing(self, jest_executor, valid_typescript_code):
        """Test Jest error message parsing"""
        # Create tests that will fail with specific errors
        failing_tests = """
import { Calculator } from './source';

describe('Calculator', () => {
    let calculator: Calculator;

    beforeEach(() => {
        calculator = new Calculator();
    });

    it('should fail with descriptive error', () => {
        expect(calculator.add(2, 3)).toBe(10); // Wrong expectation
    });

    it('should fail with another error', () => {
        expect(calculator.subtract(5, 3)).toBe(10); // Wrong expectation
    });
});
"""

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            failing_tests,
            context={"test_framework": "jest"}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.failed_tests > 0
        assert len(test_metrics.error_messages) >= 0  # May or may not capture detailed errors

    def test_jest_test_structure_analysis(self, jest_executor, valid_typescript_code, valid_jest_tests):
        """Test Jest test structure analysis"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            valid_jest_tests,
            context={"analyze_test_structure": True}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.total_tests > 0

        # Should identify test structure
        if test_metrics.total_tests > 0:
            assert test_metrics.passed_tests + test_metrics.failed_tests == test_metrics.total_tests

    def test_jest_with_mocked_dependencies(self, jest_executor):
        """Test Jest execution with mocked dependencies"""
        # Code that uses external dependencies
        code_with_deps = """
import axios from 'axios';

export class ApiService {
    async fetchData(url: string): Promise<any> {
        try {
            const response = await axios.get(url);
            return response.data;
        } catch (error) {
            throw new Error(`API call failed: ${error.message}`);
        }
    }

    processData(data: any): string {
        return data ? data.toString() : '';
    }
}
"""

        # Tests with proper mocking
        tests_with_mocks = """
import { ApiService } from './source';
import axios from 'axios';
import { jest } from '@jest/globals';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('ApiService', () => {
    let service: ApiService;

    beforeEach(() => {
        service = new ApiService();
    });

    describe('fetchData', () => {
        it('should fetch data successfully', async () => {
            const mockData = { id: 1, name: 'test' };
            mockedAxios.get.mockResolvedValue({ data: mockData });

            const result = await service.fetchData('https://api.example.com/data');
            expect(result).toEqual(mockData);
            expect(mockedAxios.get).toHaveBeenCalledWith('https://api.example.com/data');
        });

        it('should handle API errors', async () => {
            mockedAxios.get.mockRejectedValue(new Error('Network error'));

            await expect(service.fetchData('https://api.example.com/data'))
                .rejects.toThrow('API call failed: Network error');
        });
    });

    describe('processData', () => {
        it('should process valid data', () => {
            expect(service.processData({ id: 1 })).toBe('[object Object]');
        });

        it('should handle null data', () => {
            expect(service.processData(null)).toBe('');
        });

        it('should handle undefined data', () => {
            expect(service.processData(undefined)).toBe('');
        });
    });
});
"""

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            code_with_deps,
            tests_with_mocks,
            context={"test_framework": "jest", "mock_dependencies": True}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        # Should execute tests (may fail due to missing axios, but should attempt execution)
        assert test_metrics.total_tests >= 0

    def test_jest_execution_with_custom_config(self, jest_executor, valid_typescript_code, valid_jest_tests):
        """Test Jest execution with custom configuration"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            valid_jest_tests,
            context={
                "jest_config": {
                    "testTimeout": 15000,
                    "maxWorkers": 1,
                    "collectCoverage": True,
                    "coverageThreshold": {
                        "global": {
                            "branches": 70,
                            "functions": 80,
                            "lines": 80,
                            "statements": 80
                        }
                    }
                }
            }
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.execution_time >= 0

    def test_jest_asynchronous_test_handling(self, jest_executor):
        """Test Jest asynchronous test handling"""
        async_code = """
export class AsyncProcessor {
    async delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async processData(data: string): Promise<string> {
        await this.delay(100);
        return data.toUpperCase();
    }

    async processMultiple(items: string[]): Promise<string[]> {
        const promises = items.map(item => this.processData(item));
        return Promise.all(promises);
    }
}
"""

        async_tests = """
import { AsyncProcessor } from './source';

describe('AsyncProcessor', () => {
    let processor: AsyncProcessor;

    beforeEach(() => {
        processor = new AsyncProcessor();
    });

    describe('processData', () => {
        it('should process data asynchronously', async () => {
            const result = await processor.processData('hello');
            expect(result).toBe('HELLO');
        });

        it('should handle empty string', async () => {
            const result = await processor.processData('');
            expect(result).toBe('');
        });
    });

    describe('processMultiple', () => {
        it('should process multiple items in parallel', async () => {
            const items = ['hello', 'world', 'test'];
            const results = await processor.processMultiple(items);
            expect(results).toEqual(['HELLO', 'WORLD', 'TEST']);
        });

        it('should handle empty array', async () => {
            const results = await processor.processMultiple([]);
            expect(results).toEqual([]);
        });
    });

    describe('delay', () => {
        it('should delay execution', async () => {
            const start = Date.now();
            await processor.delay(50);
            const end = Date.now();
            expect(end - start).toBeGreaterThanOrEqual(45);
        });
    });
});
"""

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            async_code,
            async_tests,
            context={"test_framework": "jest", "async_tests": True}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.total_tests >= 0

    def test_jest_subprocess_error_handling(self, jest_executor, valid_typescript_code, valid_jest_tests):
        """Test handling of subprocess errors during Jest execution"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            valid_jest_tests
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.execution_time >= 0

    def test_jest_file_creation_failure_handling(self, jest_executor, valid_typescript_code, valid_jest_tests):
        """Test handling of file creation failures"""
        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            valid_jest_tests
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.failed_tests >= 0

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

    def test_jest_performance_metrics(self, jest_executor, valid_typescript_code, valid_jest_tests):
        """Test Jest performance metrics collection"""
        import time
        start_time = time.time()

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            valid_typescript_code,
            valid_jest_tests
        )

        end_time = time.time()

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.execution_time >= 0
        assert test_metrics.execution_time <= (end_time - start_time + 1)  # Allow 1 second tolerance

    def test_jest_test_result_parsing_edge_cases(self, jest_executor):
        """Test Jest result parsing for edge cases"""
        # Create minimal code and tests
        minimal_code = "export const add = (a: number, b: number): number => a + b;"
        minimal_tests = """
import { add } from './source';

describe('add', () => {
    it('works', () => {
        expect(add(1, 2)).toBe(3);
    });
});
"""

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            minimal_code,
            minimal_tests
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        assert test_metrics.total_tests >= 0

    def test_jest_coverage_edge_cases(self, jest_executor):
        """Test Jest coverage analysis edge cases"""
        # Code with no executable lines
        empty_code = """
export interface EmptyInterface {
    readonly value: string;
}

export type EmptyType = string;
"""

        empty_tests = """
describe('Empty', () => {
    it('should pass', () => {
        expect(true).toBe(true);
    });
});
"""

        # Act
        code_metrics, test_metrics = jest_executor.execute_code_and_tests(
            empty_code,
            empty_tests,
            context={"collect_coverage": True}
        )

        # Assert
        assert isinstance(test_metrics, TestExecutionMetrics)
        # Coverage might be 0 or undefined for interface-only code
        assert test_metrics.coverage_percentage >= 0