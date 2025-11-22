"""
Test fixtures for Jest execution integration tests

Provides sample TypeScript code, Jest tests, and mock responses for comprehensive testing.
"""

import json
from typing import Dict, Any


# Valid TypeScript code samples
VALID_CALCULATOR_CODE = """
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

VALID_CALCULATOR_TESTS = """
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
    });

    describe('subtract', () => {
        it('should subtract two numbers', () => {
            expect(calculator.subtract(5, 3)).toBe(2);
        });
    });

    describe('multiply', () => {
        it('should multiply two numbers', () => {
            expect(calculator.multiply(3, 4)).toBe(12);
        });
    });

    describe('divide', () => {
        it('should divide two numbers', () => {
            expect(calculator.divide(10, 2)).toBe(5);
        });

        it('should throw error when dividing by zero', () => {
            expect(() => calculator.divide(10, 0)).toThrow('Division by zero');
        });
    });
});
"""

# High coverage test samples
HIGH_COVERAGE_CODE = """
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

HIGH_COVERAGE_TESTS = """
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
    });

    describe('validateEmail', () => {
        it('should return false for null input', () => {
            expect(processor.validateEmail(null as any)).toBe(false);
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
    });

    describe('calculateLength', () => {
        it('should return 0 for null input', () => {
            expect(processor.calculateLength(null as any)).toBe(0);
        });

        it('should return 0 for empty string', () => {
            expect(processor.calculateLength('')).toBe(0);
        });

        it('should return correct length for normal string', () => {
            expect(processor.calculateLength('hello')).toBe(5);
        });
    });
});
"""

# Invalid code samples for error testing
INVALID_TYPESCRIPT_CODE = """
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

INVALID_JEST_TESTS = """
import { Calculator } from './source';

describe('Calculator', () => {
    let calculator: Calculator;

    beforeEach(() => {
        calculator = new Calculator();
    });

    describe('add', () => {
        it('should add two numbers', () => {
            expect(calculator.add(2, 3)).toBe(5);  // Valid

        it('should fail with invalid syntax', () => {  // Missing closing paren
            expect(calculator.add(2, 3)).toBe(6);  // Wrong expectation
        });
    });

    describe('divide', () => {
        it('should throw error when dividing by zero', () => {
            expect(() => calculator.divide(10, 0)).toThrow('Division by zero');  // Valid

        it('should handle invalid test syntax', () => {  // Missing closing paren
            expect(calculator.divide(10, 0)).toBe('error');  // Wrong type
        });
    });
});
"""

# Async code samples
ASYNC_PROCESSOR_CODE = """
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

ASYNC_PROCESSOR_TESTS = """
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
    });
});
"""

# Mock Jest output samples
MOCK_JEST_SUCCESS_OUTPUT = {
    "numFailedTestSuites": 0,
    "numFailedTests": 0,
    "numPassedTestSuites": 1,
    "numPassedTests": 4,
    "numPendingTestSuites": 0,
    "numPendingTests": 0,
    "numRuntimeErrorTestSuites": 0,
    "numTodoTests": 0,
    "numTotalTestSuites": 1,
    "numTotalTests": 4,
    "success": True,
    "testResults": [
        {
            "assertionResults": [
                {
                    "ancestorTitles": ["Calculator", "add"],
                    "failureMessages": [],
                    "fullName": "Calculator add should add two positive numbers",
                    "location": None,
                    "status": "passed",
                    "title": "should add two positive numbers"
                },
                {
                    "ancestorTitles": ["Calculator", "add"],
                    "failureMessages": [],
                    "fullName": "Calculator add should add positive and negative numbers",
                    "location": None,
                    "status": "passed",
                    "title": "should add positive and negative numbers"
                },
                {
                    "ancestorTitles": ["Calculator", "subtract"],
                    "failureMessages": [],
                    "fullName": "Calculator subtract should subtract two numbers",
                    "location": None,
                    "status": "passed",
                    "title": "should subtract two numbers"
                },
                {
                    "ancestorTitles": ["Calculator", "divide"],
                    "failureMessages": [],
                    "fullName": "Calculator divide should throw error when dividing by zero",
                    "location": None,
                    "status": "passed",
                    "title": "should throw error when dividing by zero"
                }
            ],
            "endTime": 1638360000000,
            "message": "",
            "name": "/tmp/test/source.test.ts",
            "startTime": 1638360000000,
            "status": "passed",
            "summary": ""
        }
    ]
}

MOCK_JEST_FAILURE_OUTPUT = {
    "numFailedTestSuites": 1,
    "numFailedTests": 2,
    "numPassedTestSuites": 0,
    "numPassedTests": 2,
    "numPendingTestSuites": 0,
    "numPendingTests": 0,
    "numRuntimeErrorTestSuites": 0,
    "numTodoTests": 0,
    "numTotalTestSuites": 1,
    "numTotalTests": 4,
    "success": False,
    "testResults": [
        {
            "assertionResults": [
                {
                    "ancestorTitles": ["Calculator", "add"],
                    "failureMessages": [],
                    "fullName": "Calculator add should add two positive numbers",
                    "location": None,
                    "status": "passed",
                    "title": "should add two positive numbers"
                },
                {
                    "ancestorTitles": ["Calculator", "add"],
                    "failureMessages": ["Expected: 10, Received: 5"],
                    "fullName": "Calculator add should fail with wrong expectation",
                    "location": None,
                    "status": "failed",
                    "title": "should fail with wrong expectation"
                },
                {
                    "ancestorTitles": ["Calculator", "subtract"],
                    "failureMessages": [],
                    "fullName": "Calculator subtract should subtract two numbers",
                    "location": None,
                    "status": "passed",
                    "title": "should subtract two numbers"
                },
                {
                    "ancestorTitles": ["Calculator", "divide"],
                    "failureMessages": ["Expected: 'error', Received: Error"],
                    "fullName": "Calculator divide should handle invalid test syntax",
                    "location": None,
                    "status": "failed",
                    "title": "should handle invalid test syntax"
                }
            ],
            "endTime": 1638360000000,
            "message": "",
            "name": "/tmp/test/source.test.ts",
            "startTime": 1638360000000,
            "status": "failed",
            "summary": ""
        }
    ]
}

MOCK_COVERAGE_REPORT = {
    "total": {
        "lines": {
            "total": 25,
            "covered": 20,
            "skipped": 0,
            "pct": 80.0
        },
        "functions": {
            "total": 5,
            "covered": 4,
            "skipped": 0,
            "pct": 80.0
        },
        "statements": {
            "total": 28,
            "covered": 22,
            "skipped": 0,
            "pct": 78.57
        },
        "branches": {
            "total": 8,
            "covered": 6,
            "skipped": 0,
            "pct": 75.0
        }
    }
}

# Jest configuration samples
JEST_CONFIG_BASIC = {
    "preset": "ts-jest",
    "testEnvironment": "node",
    "collectCoverage": True,
    "coverageReporters": ["json", "text"],
    "testTimeout": 10000,
    "setupFilesAfterEnv": []
}

JEST_CONFIG_PARALLEL = {
    "preset": "ts-jest",
    "testEnvironment": "node",
    "collectCoverage": True,
    "coverageReporters": ["json", "text"],
    "testTimeout": 10000,
    "maxWorkers": 2,
    "setupFilesAfterEnv": []
}

JEST_CONFIG_COVERAGE_THRESHOLD = {
    "preset": "ts-jest",
    "testEnvironment": "node",
    "collectCoverage": True,
    "coverageReporters": ["json", "text"],
    "testTimeout": 10000,
    "coverageThreshold": {
        "global": {
            "branches": 70,
            "functions": 80,
            "lines": 80,
            "statements": 80
        }
    }
}

# Package.json samples
PACKAGE_JSON_BASIC = {
    "name": "test-validation",
    "version": "1.0.0",
    "scripts": {"test": "jest"},
    "devDependencies": {
        "@types/jest": "^29.0.0",
        "jest": "^29.0.0",
        "ts-jest": "^29.0.0",
        "@types/node": "^20.0.0",
        "typescript": "^5.0.0"
    }
}

PACKAGE_JSON_WITH_DEPS = {
    "name": "test-validation",
    "version": "1.0.0",
    "scripts": {"test": "jest"},
    "dependencies": {
        "axios": "^1.0.0"
    },
    "devDependencies": {
        "@types/jest": "^29.0.0",
        "jest": "^29.0.0",
        "ts-jest": "^29.0.0",
        "@types/node": "^20.0.0",
        "typescript": "^5.0.0"
    }
}

# Helper functions for creating test data
def create_mock_jest_result(success: bool = True, total_tests: int = 4, passed_tests: int = 4,
                          failed_tests: int = 0, coverage_pct: float = 85.0) -> Dict[str, Any]:
    """Create a mock Jest test result"""
    return {
        "numFailedTestSuites": 1 if failed_tests > 0 else 0,
        "numFailedTests": failed_tests,
        "numPassedTestSuites": 1 if passed_tests > 0 else 0,
        "numPassedTests": passed_tests,
        "numPendingTestSuites": 0,
        "numPendingTests": 0,
        "numRuntimeErrorTestSuites": 0,
        "numTodoTests": 0,
        "numTotalTestSuites": 1,
        "numTotalTests": total_tests,
        "success": success,
        "testResults": [
            {
                "assertionResults": [
                    {
                        "ancestorTitles": ["TestSuite"],
                        "failureMessages": ["Mock failure"] if failed_tests > 0 else [],
                        "fullName": f"TestSuite test {i+1}",
                        "location": None,
                        "status": "failed" if i < failed_tests else "passed",
                        "title": f"test {i+1}"
                    } for i in range(total_tests)
                ],
                "endTime": 1638360000000,
                "message": "",
                "name": "/tmp/test/source.test.ts",
                "startTime": 1638360000000,
                "status": "failed" if failed_tests > 0 else "passed",
                "summary": ""
            }
        ]
    }

def create_mock_coverage_report(lines_pct: float = 85.0, functions_pct: float = 90.0,
                               statements_pct: float = 82.0, branches_pct: float = 75.0) -> Dict[str, Any]:
    """Create a mock coverage report"""
    return {
        "total": {
            "lines": {
                "total": 100,
                "covered": int(100 * lines_pct / 100),
                "skipped": 0,
                "pct": lines_pct
            },
            "functions": {
                "total": 10,
                "covered": int(10 * functions_pct / 100),
                "skipped": 0,
                "pct": functions_pct
            },
            "statements": {
                "total": 120,
                "covered": int(120 * statements_pct / 100),
                "skipped": 0,
                "pct": statements_pct
            },
            "branches": {
                "total": 20,
                "covered": int(20 * branches_pct / 100),
                "skipped": 0,
                "pct": branches_pct
            }
        }
    }