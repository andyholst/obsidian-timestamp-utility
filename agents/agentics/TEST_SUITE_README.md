# LLM Test Suite Validator

A comprehensive testing framework for validating LLM-generated TypeScript code and tests, ensuring they work correctly together and follow best practices.

## Overview

The LLM Test Suite Validator provides a complete validation pipeline that:

- **Executes** generated TypeScript code in sandboxed environments
- **Runs** generated tests using Jest
- **Validates** the relationship between code and tests
- **Assesses** LangChain best practices compliance
- **Integrates** with the existing code validator framework
- **Generates** detailed reports with actionable recommendations

## Key Features

### 🔧 Code Execution
- Sandboxed TypeScript execution with Node.js
- Automatic export detection and smoke testing
- Timeout protection and memory limits
- Comprehensive error reporting

### 🧪 Test Execution
- Full Jest test suite execution
- Coverage analysis and reporting
- Parallel test execution support
- Detailed failure diagnostics

### 🔗 Relationship Validation
- Test-code coverage analysis
- Assertion quality assessment
- Mock usage detection
- Edge case coverage evaluation

### 🏗️ LangChain Compliance
- LCEL (LangChain Expression Language) usage detection
- Error handling pattern validation
- State management assessment
- Tool integration verification
- Composability scoring

### 📊 Reporting
- Comprehensive markdown reports
- Risk level assessment (Low/Medium/High/Critical)
- Actionable recommendations
- Integration with code validator framework

## Installation

The test suite is part of the agentics package. Ensure you have the required dependencies:

```bash
# Install project dependencies
npm install
pip install -r requirements.txt

# For TypeScript execution
npm install -g typescript ts-node

# For testing
npm install -g jest @types/jest ts-jest
```

## Quick Start

### Basic Usage

```python
from src.test_suite import validate_llm_test_suite, generate_test_suite_report

# Your LLM-generated code and tests
code = """
export class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }
}
"""

tests = """
describe('Calculator', () => {
    it('should add numbers', () => {
        const calc = new Calculator();
        expect(calc.add(2, 3)).toBe(5);
    });
});
"""

# Validate the code and tests
result = validate_llm_test_suite(code, tests)

# Generate detailed report
report = generate_test_suite_report(code, tests, result)
print(report)
```

### Advanced Usage with Custom Context

```python
from src.test_suite import LLMTestSuiteValidator

validator = LLMTestSuiteValidator()

result = validator.validate_test_suite(
    code,
    tests,
    context={
        "language": "typescript",
        "framework": "react",
        "test_framework": "jest",
        "domain": "ui_components"
    },
    include_code_validator=True  # Integrate with code validator
)

# Access detailed metrics
print(f"Score: {result.overall_score}")
print(f"Coverage: {result.test_execution.coverage_percentage}%")
print(f"Risk Level: {result.risk_level.value}")
```

## API Reference

### Core Functions

#### `validate_llm_test_suite(code, tests, context=None, include_code_validator=True)`

Main validation function that returns a `TestSuiteValidationResult`.

**Parameters:**
- `code` (str): The generated TypeScript code to validate
- `tests` (str): The generated test code to run
- `context` (dict, optional): Additional context information
- `include_code_validator` (bool): Whether to integrate with code validator framework

**Returns:** `TestSuiteValidationResult` object

#### `generate_test_suite_report(code, tests, result, code_validator_report=None)`

Generates a comprehensive markdown report.

**Parameters:**
- `code` (str): The validated code
- `tests` (str): The validated tests
- `result` (TestSuiteValidationResult): Validation results
- `code_validator_report` (ValidationReport, optional): Code validator results

**Returns:** Markdown formatted report string

### Classes

#### `LLMTestSuiteValidator`

Main validator class with full control over validation process.

**Methods:**
- `validate_test_suite(code, tests, context=None, include_code_validator=True)`
- `generate_detailed_report(code, tests, result, code_validator_report=None)`

#### `TestSuiteValidationResult`

Contains all validation results and metrics.

**Key Attributes:**
- `overall_score` (float): 0-100 overall quality score
- `risk_level` (TestSuiteRiskLevel): LOW, MEDIUM, HIGH, or CRITICAL
- `code_execution` (CodeExecutionMetrics): Code execution results
- `test_execution` (TestExecutionMetrics): Test execution results
- `test_code_relationship` (TestCodeRelationship): Code-test relationship analysis
- `langchain_compliance` (LangChainCompliance): LangChain best practices compliance
- `critical_issues` (List[str]): Critical problems found
- `warnings` (List[str]): Warning messages
- `suggestions` (List[str]): Improvement suggestions

## Validation Metrics

### Code Execution Metrics
- **Success**: Whether code executed without errors
- **Execution Time**: Time taken to run code
- **Output Lines**: Number of output lines generated
- **Error Count**: Number of errors encountered
- **Timeout Occurred**: Whether execution timed out

### Test Execution Metrics
- **Total Tests**: Number of tests found
- **Passed/Failed/Skipped**: Test results breakdown
- **Coverage Percentage**: Code coverage achieved
- **Execution Time**: Time taken to run tests
- **Error Messages**: Detailed failure information

### Test-Code Relationship
- **Test Coverage**: Percentage of code covered by tests
- **Assertion Quality**: Quality score of test assertions (0-10)
- **Mock Usage**: Whether mocks are used appropriately
- **Edge Case Coverage**: Number of edge cases tested
- **Integration/Unit Test Counts**: Breakdown of test types

### LangChain Compliance
- **LCEL Usage**: Whether LangChain Expression Language is used
- **Error Handling Score**: Quality of error handling (0-10)
- **State Management Score**: Quality of state management (0-10)
- **Composability Score**: How well code composes (0-10)
- **Tool Integration Score**: Quality of tool integration (0-10)
- **Overall Compliance**: Combined compliance score (0-10)

## Risk Assessment

The validator assigns risk levels based on overall scores:

- **LOW** (80-100): High quality, safe to use
- **MEDIUM** (60-79): Good quality with minor issues
- **HIGH** (40-59): Significant issues requiring attention
- **CRITICAL** (0-39): Major problems, not recommended for use

## Integration with Code Validator

The test suite integrates seamlessly with the existing `code_validator.py` framework:

```python
from src.code_validator import validate_generated_code
from src.test_suite import generate_test_suite_report

# Run both validations
code_validator_result = validate_generated_code(code, tests)
test_suite_result = validate_llm_test_suite(code, tests)

# Generate combined report
report = generate_test_suite_report(
    code,
    tests,
    test_suite_result,
    code_validator_result
)
```

## Configuration

### Environment Variables

- `TEST_EXECUTION_TIMEOUT`: Maximum execution time in milliseconds (default: 30000)
- `TEST_MEMORY_LIMIT`: Memory limit for execution (default: 256MB)
- `TS_EXECUTION_TIMEOUT`: TypeScript execution timeout (default: 5000)

### Jest Configuration

The validator automatically configures Jest with:
- TypeScript support via `ts-jest`
- Coverage collection and reporting
- 30-second test timeout
- JSON output for parsing

## Examples

See `src/test_suite_examples.py` for comprehensive examples including:

- Basic TypeScript service validation
- LangChain agent validation
- React component testing
- Error handling scenarios
- Advanced configuration options

Run examples with:
```bash
python src/test_suite_examples.py
```

## Best Practices

### For LLM Code Generation

1. **Include comprehensive tests** with good assertion coverage
2. **Use TypeScript** for better type safety validation
3. **Follow LangChain patterns** when building agentics code
4. **Handle edge cases** in both code and tests
5. **Use appropriate mocking** for external dependencies

### For Validation

1. **Always include context** information for better analysis
2. **Review critical issues** before using generated code
3. **Check coverage metrics** to ensure adequate testing
4. **Validate LangChain compliance** for agentics code
5. **Use detailed reports** for improvement feedback

## Troubleshooting

### Common Issues

**Code execution fails:**
- Check for syntax errors in generated code
- Ensure all dependencies are available
- Review timeout settings

**Tests not running:**
- Verify Jest is installed globally
- Check test file syntax
- Ensure proper TypeScript configuration

**Low coverage scores:**
- Add more comprehensive tests
- Include edge cases and error scenarios
- Test all code paths

**LangChain compliance issues:**
- Use LCEL patterns for chaining
- Implement proper error handling
- Follow state management best practices

### Debug Mode

Enable debug logging for detailed validation information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

result = validate_llm_test_suite(code, tests)
```

## Contributing

When adding new validation features:

1. Add unit tests in `tests/unit/test_test_suite_unit.py`
2. Add integration tests in `tests/integration/test_test_suite_integration.py`
3. Update examples in `src/test_suite_examples.py`
4. Update this documentation

## License

This module is part of the Obsidian Timestamp Utility project and follows the same license terms.