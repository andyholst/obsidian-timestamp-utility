"""
Comprehensive Test Suite for LLM-Generated TypeScript Code and Tests

This module provides a complete testing framework that validates LLM-generated TypeScript code
and tests, ensuring they work correctly together and follow best practices.
"""

import os
import re
import ast
import json
import time
import logging
import tempfile
import subprocess
from typing import Dict, Any, List, Optional, Tuple, NamedTuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from .code_validator import (
    validate_generated_code,
    ValidationReport,
    TestResult,
    ExecutionResult,
    ChainValidation,
    RiskLevel
)
from .utils import log_info
from .monitoring import structured_log


class SuiteRiskLevel(Enum):
    """Risk levels for test suite validation"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TestExecutionMetrics:
    """Metrics from test execution"""
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    execution_time: float = 0.0
    coverage_percentage: float = 0.0
    error_messages: List[str] = field(default_factory=list)


@dataclass
class CodeExecutionMetrics:
    """Metrics from code execution"""
    success: bool = False
    execution_time: float = 0.0
    output_lines: int = 0
    error_count: int = 0
    memory_usage: int = 0
    timeout_occurred: bool = False


@dataclass
class TestCodeRelationship:
    """Analysis of relationship between tests and code"""
    test_coverage: float = 0.0
    assertion_quality: float = 0.0
    mock_usage: bool = False
    edge_case_coverage: int = 0
    integration_test_count: int = 0
    unit_test_count: int = 0


@dataclass
class LangChainCompliance:
    """LangChain best practices compliance"""
    lcel_usage: bool = False
    error_handling_score: float = 0.0
    state_management_score: float = 0.0
    composability_score: float = 0.0
    tool_integration_score: float = 0.0
    overall_compliance: float = 0.0


@dataclass
class SuiteValidationResult:
    """Comprehensive test suite validation result"""
    timestamp: datetime = field(default_factory=datetime.now)
    code_hash: str = ""
    test_hash: str = ""

    # Execution Results
    code_execution: CodeExecutionMetrics = field(default_factory=CodeExecutionMetrics)
    test_execution: TestExecutionMetrics = field(default_factory=TestExecutionMetrics)

    # Relationship Analysis
    test_code_relationship: TestCodeRelationship = field(default_factory=TestCodeRelationship)

    # Pattern Compliance
    langchain_compliance: LangChainCompliance = field(default_factory=LangChainCompliance)

    # Quality Metrics
    overall_score: float = 0.0
    risk_level: SuiteRiskLevel = SuiteRiskLevel.LOW

    # Recommendations
    critical_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Generate markdown report"""
        return f"""
# Test Suite Validation Report

**Generated:** {self.timestamp}
**Code Hash:** {self.code_hash}
**Test Hash:** {self.test_hash}
**Overall Score:** {self.overall_score:.1f}/100
**Risk Level:** {self.risk_level.value.upper()}

## Code Execution Results
- **Success:** {"✅" if self.code_execution.success else "❌"}
- **Execution Time:** {self.code_execution.execution_time:.2f}s
- **Output Lines:** {self.code_execution.output_lines}
- **Errors:** {self.code_execution.error_count}
- **Memory Usage:** {self.code_execution.memory_usage}MB
- **Timeout:** {"Yes" if self.code_execution.timeout_occurred else "No"}

## Test Execution Results
- **Total Tests:** {self.test_execution.total_tests}
- **Passed:** {self.test_execution.passed_tests}
- **Failed:** {self.test_execution.failed_tests}
- **Skipped:** {self.test_execution.skipped_tests}
- **Coverage:** {self.test_execution.coverage_percentage:.1f}%
- **Execution Time:** {self.test_execution.execution_time:.2f}s

## Test-Code Relationship
- **Test Coverage:** {self.test_code_relationship.test_coverage:.1f}%
- **Assertion Quality:** {self.test_code_relationship.assertion_quality:.1f}/10
- **Mock Usage:** {"Yes" if self.test_code_relationship.mock_usage else "No"}
- **Edge Cases Covered:** {self.test_code_relationship.edge_case_coverage}
- **Integration Tests:** {self.test_code_relationship.integration_test_count}
- **Unit Tests:** {self.test_code_relationship.unit_test_count}

## LangChain Compliance
- **LCEL Usage:** {"✅" if self.langchain_compliance.lcel_usage else "❌"}
- **Error Handling:** {self.langchain_compliance.error_handling_score:.1f}/10
- **State Management:** {self.langchain_compliance.state_management_score:.1f}/10
- **Composability:** {self.langchain_compliance.composability_score:.1f}/10
- **Tool Integration:** {self.langchain_compliance.tool_integration_score:.1f}/10
- **Overall Compliance:** {self.langchain_compliance.overall_compliance:.1f}/10

## Critical Issues
{chr(10).join(f"- {issue}" for issue in self.critical_issues)}

## Warnings
{chr(10).join(f"- {warning}" for warning in self.warnings)}

## Suggestions
{chr(10).join(f"- {suggestion}" for suggestion in self.suggestions)}
"""


class TestSuiteExecutor:
    """Executes generated TypeScript code and tests in isolated environments"""

    def __init__(self):
        self.monitor = structured_log(__name__)
        self.execution_timeout = int(os.getenv('TEST_EXECUTION_TIMEOUT', '30000'))
        self.memory_limit = os.getenv('TEST_MEMORY_LIMIT', '256MB')

    def execute_code_and_tests(
        self,
        code: str,
        tests: str,
        context: Dict[str, Any] = None
    ) -> Tuple[CodeExecutionMetrics, TestExecutionMetrics]:
        """Execute both code and tests, returning comprehensive metrics"""
        context = context or {}

        # Execute the generated code
        code_metrics = self._execute_generated_code(code, context)

        # Execute the tests against the code
        test_metrics = self._execute_tests(tests, code, context)

        return code_metrics, test_metrics

    def _execute_generated_code(self, code: str, context: Dict[str, Any]) -> CodeExecutionMetrics:
        """Execute the generated TypeScript code in sandbox"""
        start_time = time.time()

        try:
            # Create temporary directory for execution
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write code to file
                code_file = os.path.join(temp_dir, 'generated.ts')
                with open(code_file, 'w') as f:
                    f.write(code)

                # Create a simple test harness
                harness_code = f"""
import {{ {self._extract_exports(code)} }} from './generated';

console.log('Code loaded successfully');

// Basic smoke test - try to instantiate main exports
try {{
    {self._generate_smoke_test(code)}
    console.log('Smoke test passed');
}} catch (error) {{
    console.error('Smoke test failed:', error.message);
    process.exit(1);
}}
"""
                harness_file = os.path.join(temp_dir, 'harness.ts')
                with open(harness_file, 'w') as f:
                    f.write(harness_code)

                # Get memory limit from sandbox config
                memory_limit = context.get('sandbox_config', {}).get('memory_limit', self.memory_limit)
                if memory_limit.endswith('MB'):
                    memory_mb = int(memory_limit[:-2])
                else:
                    memory_mb = int(memory_limit)

                # Execute with Node.js
                result = subprocess.run(
                    ['npx', 'ts-node', '--max-old-space-size', str(memory_mb), harness_file],
                    capture_output=True,
                    text=True,
                    timeout=self.execution_timeout / 1000,
                    cwd=temp_dir
                )

                execution_time = time.time() - start_time

                return CodeExecutionMetrics(
                    success=result.returncode == 0,
                    execution_time=execution_time,
                    output_lines=len(result.stdout.strip().split('\n')) if result.stdout else 0,
                    error_count=len(result.stderr.strip().split('\n')) if result.stderr else 0,
                    timeout_occurred=False
                )

        except subprocess.TimeoutExpired:
            return CodeExecutionMetrics(
                success=False,
                execution_time=time.time() - start_time,
                timeout_occurred=True
            )
        except Exception as e:
            self.monitor.error(f"Code execution failed: {str(e)}")
            return CodeExecutionMetrics(
                success=False,
                execution_time=time.time() - start_time,
                error_count=1
            )

    def _execute_tests(self, test_code: str, source_code: str, context: Dict[str, Any]) -> TestExecutionMetrics:
        """Execute tests using Jest and collect comprehensive metrics"""
        start_time = time.time()

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write source and test files
                source_file = os.path.join(temp_dir, 'source.ts')
                test_file = os.path.join(temp_dir, 'source.test.ts')

                with open(source_file, 'w') as f:
                    f.write(source_code)
                with open(test_file, 'w') as f:
                    f.write(test_code)

                # Create Jest config
                jest_config = {
                    "preset": "ts-jest",
                    "testEnvironment": "node",
                    "collectCoverage": True,
                    "coverageReporters": ["json-summary", "text"],
                    "testTimeout": self.execution_timeout,
                    "setupFilesAfterEnv": []
                }

                config_file = os.path.join(temp_dir, 'jest.config.js')
                with open(config_file, 'w') as f:
                    f.write(f'module.exports = {json.dumps(jest_config, indent=2)};')

                # Create package.json
                package_json = {
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

                with open(os.path.join(temp_dir, 'package.json'), 'w') as f:
                    json.dump(package_json, f, indent=2)

                # Install dependencies (if npm available)
                try:
                    subprocess.run(['npm', 'install'], cwd=temp_dir,
                                 capture_output=True, timeout=30)
                except:
                    pass

                # Run Jest
                result = subprocess.run(
                    ['npx', 'jest', '--config', config_file, '--coverage', '--verbose', '--json'],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=self.execution_timeout / 1000
                )

                print(f"DEBUG_JEST: returncode={result.returncode}")
                print(f"DEBUG_JEST: stdout_len={len(result.stdout)}")
                print(f"DEBUG_JEST: stderr_len={len(result.stderr)}")
                print(f"DEBUG_JEST: stdout_snip={result.stdout[:500]}")

                coverage_dir = os.path.join(temp_dir, 'coverage')
                print(f"DEBUG_COVERAGE: coverage_dir_exists={os.path.exists(coverage_dir)}")
                if os.path.exists(coverage_dir):
                    print(f"DEBUG_COVERAGE: coverage_files={os.listdir(coverage_dir)}")

                execution_time = time.time() - start_time

                # Parse Jest output
                metrics = self._parse_jest_results(result.stdout, result.stderr, temp_dir)

                return TestExecutionMetrics(
                    total_tests=metrics['total'],
                    passed_tests=metrics['passed'],
                    failed_tests=metrics['failed'],
                    skipped_tests=metrics['skipped'],
                    execution_time=execution_time,
                    coverage_percentage=metrics['coverage'],
                    error_messages=metrics['errors']
                )

        except subprocess.TimeoutExpired:
            return TestExecutionMetrics(
                execution_time=time.time() - start_time,
                error_messages=["Test execution timeout"]
            )
        except Exception as e:
            self.monitor.error(f"Test execution failed: {str(e)}")
            return TestExecutionMetrics(
                execution_time=time.time() - start_time,
                error_messages=[str(e)]
            )

    def _extract_exports(self, code: str) -> str:
        """Extract export names from TypeScript code"""
        exports = []
        # Simple regex to find exports
        export_matches = re.findall(r'export\s+(?:class|function|const|let|var)\s+(\w+)', code)
        exports.extend(export_matches)

        # Also find default exports
        if 'export default' in code:
            exports.append('default')

        return ', '.join(exports) if exports else '*'

    def _generate_smoke_test(self, code: str) -> str:
        """Generate basic smoke test code"""
        smoke_tests = []

        # Check for class exports
        class_matches = re.findall(r'export\s+class\s+(\w+)', code)
        for class_name in class_matches:
            smoke_tests.append(f'new {class_name}();')

        # Check for function exports
        func_matches = re.findall(r'export\s+function\s+(\w+)', code)
        for func_name in func_matches:
            smoke_tests.append(f'{func_name}();')

        return '\n'.join(smoke_tests) if smoke_tests else '// No smoke tests generated'

    def _parse_jest_results(self, stdout: str, stderr: str, temp_dir: str) -> Dict[str, Any]:
        """Parse Jest JSON output for metrics"""
        metrics = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'coverage': 0.0,
            'errors': []
        }

        try:
            # Try to parse JSON output
            if stdout:
                result_data = json.loads(stdout)
                # Parse top-level Jest summary for error cases
                num_runtime_errors = result_data.get('numRuntimeErrorTestSuites', 0)
                num_failed_suites = result_data.get('numFailedTestSuites', 0)
                num_failed_tests_summary = result_data.get('numFailedTests', 0)
                num_total_tests = result_data.get('numTotalTests', 0)
                num_passed_tests = result_data.get('numPassedTests', 0)
                num_skipped_tests = result_data.get('numPendingTests', 0) + result_data.get('numSkippedTests', 0)
                
                # Parse detailed test results if available
                detailed_parsed = False
                if 'testResults' in result_data:
                    detailed_parsed = True
                    for test_file in result_data['testResults']:
                        for test_result in test_file['assertionResults']:
                            metrics['total'] += 1
                            if test_result['status'] == 'passed':
                                metrics['passed'] += 1
                            elif test_result['status'] == 'failed':
                                metrics['failed'] += 1
                                if test_result.get('failureMessages'):
                                    metrics['errors'].append(test_result['failureMessages'][0])
                            elif test_result['status'] in ['skipped', 'pending']:
                                metrics['skipped'] += 1
                
                if not detailed_parsed:
                    metrics['total'] = num_total_tests + num_runtime_errors + num_failed_suites
                    metrics['passed'] = num_passed_tests
                    metrics['failed'] = num_failed_tests_summary + num_runtime_errors + num_failed_suites
                    metrics['skipped'] = num_skipped_tests
                
                # Extract errors from stderr always
                if stderr.strip():
                    error_lines = []
                    for line in stderr.splitlines()[-10:]:
                        stripped = line.strip()
                        if stripped and ('error' in stripped.lower() or 'fail' in stripped.lower() or 'referenceerror' in stripped.lower()):
                            error_lines.append(stripped)
                    metrics['errors'].extend(error_lines[:3])
                
                # Deduplicate and limit errors
                unique_errors = list(dict.fromkeys(metrics['errors']))  # preserve order
                metrics['errors'] = unique_errors[:5]

            # Parse coverage from coverage report
            coverage_file = os.path.join(temp_dir, 'coverage', 'coverage-summary.json')
            print(f"DEBUG_PARSE: coverage_file={coverage_file}, exists={os.path.exists(coverage_file)}")
            if os.path.exists(coverage_file):
                with open(coverage_file, 'r') as f:
                    coverage_data = json.load(f)
                    print(f"DEBUG_PARSE: coverage_data={str(coverage_data)[:1000]}")
                    if 'total' in coverage_data and 'lines' in coverage_data['total']:
                        pct = coverage_data['total']['lines'].get('pct', 0.0)
                        if isinstance(pct, str):
                            if pct == 'Unknown':
                                metrics['coverage'] = 0.0
                            else:
                                try:
                                    metrics['coverage'] = float(pct)
                                except (ValueError, TypeError):
                                    metrics['coverage'] = 0.0
                        else:
                            metrics['coverage'] = float(pct)

        except (json.JSONDecodeError, KeyError):
            # Fallback to regex parsing
            lines = stdout.split('\n')
            for line in lines:
                if 'Tests:' in line and 'passed' in line:
                    match = re.search(r'Tests:\s*(\d+)\s*passed,\s*(\d+)\s*failed', line)
                    if match:
                        metrics['passed'] = int(match.group(1))
                        metrics['failed'] = int(match.group(2))
                        metrics['total'] = metrics['passed'] + metrics['failed']

        return metrics


class AssertionValidator:
    """Validates test assertions using AST parsing"""

    def __init__(self):
        self.monitor = structured_log(__name__)

    def validate_assertions(self, test_code: str) -> Dict[str, Any]:
        """Validate assertions in test code using AST analysis or Jest regex"""
        # Check if this looks like Jest/TypeScript code
        if self._is_jest_code(test_code):
            print(f"DEBUG: Detected Jest code, using regex analysis")
            return {
                'assertion_count': self._count_jest_assertions(test_code),
                'assertion_types': self._categorize_jest_assertions(test_code),
                'test_structure': self._analyze_jest_structure(test_code),
                'mock_usage': self._analyze_jest_mock_usage(test_code)
            }
        else:
            # Try Python AST analysis
            try:
                ast_tree = self._parse_test_code(test_code)
                return {
                    'assertion_count': self._count_assertions(ast_tree),
                    'assertion_types': self._categorize_assertions(ast_tree),
                    'test_structure': self._analyze_test_structure(ast_tree),
                    'mock_usage': self._analyze_mock_patterns(ast_tree)
                }
            except Exception as e:
                self.monitor.warning(f"Failed to parse test code: {str(e)}")
                return {
                    'assertion_count': 0,
                    'assertion_types': {},
                    'test_structure': {},
                    'mock_usage': False
                }

    def _parse_test_code(self, test_code: str) -> ast.Module:
        """Parse test code into AST"""
        return ast.parse(test_code)

    def _count_assertions(self, ast_tree: ast.Module) -> int:
        """Count total assertions in the test code"""
        count = 0

        class AssertionVisitor(ast.NodeVisitor):
            def visit_Assert(self, node):
                nonlocal count
                count += 1
                self.generic_visit(node)

            def visit_Call(self, node):
                # Count unittest-style assertions (self.assert*)
                if (isinstance(node.func, ast.Attribute) and
                    isinstance(node.func.value, ast.Name) and
                    node.func.value.id == 'self' and
                    node.func.attr.startswith('assert')):
                    nonlocal count
                    count += 1
                self.generic_visit(node)

        visitor = AssertionVisitor()
        visitor.visit(ast_tree)
        return count

    def _categorize_assertions(self, ast_tree: ast.Module) -> Dict[str, int]:
        """Categorize assertions by type"""
        categories = {
            'equality': 0,
            'truthiness': 0,
            'exceptions': 0,
            'mock_verification': 0,
            'type_checking': 0,
            'other': 0
        }

        class CategorizationVisitor(ast.NodeVisitor):
            def visit_Assert(self, node):
                # Simple assert statements - categorize based on content
                if isinstance(node.test, ast.Compare):
                    categories['equality'] += 1
                elif isinstance(node.test, ast.Name) or isinstance(node.test, ast.Attribute):
                    categories['truthiness'] += 1
                else:
                    categories['other'] += 1
                self.generic_visit(node)

            def visit_Call(self, node):
                if (isinstance(node.func, ast.Attribute) and
                    isinstance(node.func.value, ast.Name) and
                    node.func.value.id == 'self'):
                    attr = node.func.attr
                    if attr in ['assertEqual', 'assertNotEqual', 'assertAlmostEqual']:
                        categories['equality'] += 1
                    elif attr in ['assertTrue', 'assertFalse', 'assertIsNone', 'assertIsNotNone']:
                        categories['truthiness'] += 1
                    elif attr in ['assertRaises', 'assertRaisesRegex']:
                        categories['exceptions'] += 1
                    elif 'mock' in attr.lower() or 'call' in attr.lower():
                        categories['mock_verification'] += 1
                    elif 'type' in attr.lower() or 'instance' in attr.lower():
                        categories['type_checking'] += 1
                    else:
                        categories['other'] += 1
                self.generic_visit(node)

        visitor = CategorizationVisitor()
        visitor.visit(ast_tree)
        return categories

    def _analyze_test_structure(self, ast_tree: ast.Module) -> Dict[str, Any]:
        """Analyze the structure of test code"""
        structure = {
            'test_functions': 0,
            'test_classes': 0,
            'setup_methods': 0,
            'teardown_methods': 0,
            'total_functions': 0,
            'total_classes': 0
        }

        class StructureVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                structure['total_functions'] += 1
                if node.name.startswith('test_'):
                    structure['test_functions'] += 1
                elif node.name in ['setUp', 'tearDown', 'setup_method', 'teardown_method']:
                    if 'set' in node.name.lower():
                        structure['setup_methods'] += 1
                    else:
                        structure['teardown_methods'] += 1
                self.generic_visit(node)

            def visit_ClassDef(self, node):
                structure['total_classes'] += 1
                if node.name.startswith('Test'):
                    structure['test_classes'] += 1
                self.generic_visit(node)

        visitor = StructureVisitor()
        visitor.visit(ast_tree)
        return structure

    def _analyze_mock_patterns(self, ast_tree: ast.Module) -> bool:
        """Detect mock usage patterns"""
        mock_found = False

        class MockVisitor(ast.NodeVisitor):
            def visit_Import(self, node):
                nonlocal mock_found
                for alias in node.names:
                    if 'mock' in alias.name.lower() or 'MagicMock' in alias.name:
                        mock_found = True
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                nonlocal mock_found
                if 'unittest.mock' in node.module or 'mock' in node.module:
                    mock_found = True
                for alias in node.names:
                    if 'mock' in alias.name.lower() or 'MagicMock' in alias.name:
                        mock_found = True
                self.generic_visit(node)

            def visit_Call(self, node):
                nonlocal mock_found
                # Check for mock instantiation
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['Mock', 'MagicMock', 'patch']:
                        mock_found = True
                elif isinstance(node.func, ast.Attribute):
                    if 'mock' in node.func.attr.lower() or node.func.attr in ['patch', 'Mock', 'MagicMock']:
                        mock_found = True
                self.generic_visit(node)

        visitor = MockVisitor()
        visitor.visit(ast_tree)
        return mock_found
    def _count_jest_assertions(self, test_code: str) -> int:
        """Count Jest expect() assertions"""
        # Count expect() calls
        expect_count = len(re.findall(r'expect\s*\(', test_code))
        return expect_count

    def _categorize_jest_assertions(self, test_code: str) -> Dict[str, int]:
        """Categorize Jest assertions by type"""
        categories = {
            'equality': 0,
            'truthiness': 0,
            'exceptions': 0,
            'mock_verification': 0,
            'type_checking': 0,
            'other': 0
        }

        # Count different Jest matchers
        if re.search(r'\.toBe\(', test_code):
            categories['equality'] += 1
        if re.search(r'\.toEqual\(', test_code):
            categories['equality'] += 1
        if re.search(r'\.toBeTruthy\(|toBeFalsy\(', test_code):
            categories['truthiness'] += 1
        if re.search(r'\.toThrow\(', test_code):
            categories['exceptions'] += 1
        if re.search(r'\.toHaveBeenCalled\(', test_code):
            categories['mock_verification'] += 1
        if re.search(r'\.toBeDefined\(|toBeUndefined\(', test_code):
            categories['type_checking'] += 1

        return categories

    def _analyze_jest_structure(self, test_code: str) -> Dict[str, Any]:
        """Analyze Jest test structure"""
        structure = {
            'test_functions': len(re.findall(r'it\s*\(', test_code)),
            'test_classes': 0,  # Jest doesn't use classes like unittest
            'setup_methods': len(re.findall(r'beforeEach\s*\(|beforeAll\s*\(', test_code)),
            'teardown_methods': len(re.findall(r'afterEach\s*\(|afterAll\s*\(', test_code)),
            'total_functions': len(re.findall(r'it\s*\(', test_code)),  # Approximate
            'total_classes': 0
        }
        return structure
    def _is_jest_code(self, test_code: str) -> bool:
        """Check if the test code looks like Jest/TypeScript"""
        jest_indicators = [
            r'expect\s*\(',
            r'describe\s*\(',
            r'it\s*\(',
            r'\.toBe\(',
            r'\.toEqual\(',
            r'jest\.'
        ]
        return any(re.search(pattern, test_code) for pattern in jest_indicators)

    def _analyze_jest_mock_usage(self, test_code: str) -> bool:
        """Detect Jest mock usage"""
        mock_patterns = [
            r'jest\.mock\(',
            r'jest\.fn\(\)',
            r'jest\.spyOn\(',
            r'mockImplementation\(',
            r'mockReturnValue\('
        ]
        return any(re.search(pattern, test_code) for pattern in mock_patterns)


class TestSuiteValidator:
    """Validates the relationship between generated tests and code"""

    def __init__(self):
        self.monitor = structured_log(__name__)
        self.assertion_validator = AssertionValidator()

    def validate_test_code_relationship(
        self,
        test_code: str,
        source_code: str,
        test_metrics: TestExecutionMetrics
    ) -> TestCodeRelationship:
        """Analyze the relationship between tests and source code"""

        relationship = TestCodeRelationship()

        # Analyze test coverage
        relationship.test_coverage = test_metrics.coverage_percentage

        # Analyze assertion quality
        relationship.assertion_quality = self._analyze_assertion_quality(test_code)

        # Check for mock usage
        relationship.mock_usage = self._detect_mock_usage(test_code)

        # Count edge cases
        relationship.edge_case_coverage = self._count_edge_cases(test_code)

        # Categorize tests
        test_counts = self._categorize_tests(test_code)
        relationship.integration_test_count = test_counts['integration']
        relationship.unit_test_count = test_counts['unit']

        return relationship

    def _analyze_assertion_quality(self, test_code: str) -> float:
        """Analyze the quality of test assertions (0-10 scale) using AST"""
        analysis = self.assertion_validator.validate_assertions(test_code)
        print(f"DEBUG: Assertion analysis result: {analysis}")

        score = 0.0
        assertion_count = analysis['assertion_count']
        assertion_types = analysis['assertion_types']
        print(f"DEBUG: Assertion count: {assertion_count}, types: {assertion_types}")

        # Base score from assertion count
        if assertion_count > 0:
            score += min(5.0, assertion_count * 0.5)

        # Bonus for assertion diversity
        diverse_types = sum(1 for count in assertion_types.values() if count > 0)
        score += min(3.0, diverse_types * 0.5)

        # Bonus for comprehensive assertion types
        if assertion_types.get('exceptions', 0) > 0:
            score += 1.0
        if assertion_types.get('mock_verification', 0) > 0:
            score += 1.0

        log_info(__name__, f"Final assertion quality score: {score}")
        return min(10.0, score)

    def _detect_mock_usage(self, test_code: str) -> bool:
        """Detect if mocks are used in tests using AST"""
        analysis = self.assertion_validator.validate_assertions(test_code)
        return analysis['mock_usage']

    def _count_edge_cases(self, test_code: str) -> int:
        """Count edge case test scenarios"""
        edge_case_patterns = [
            r'null|undefined',
            r'empty|blank',
            r'max|min',
            r'boundary',
            r'edge',
            r'error|exception',
            r'invalid|malformed'
        ]

        edge_cases = 0
        for pattern in edge_case_patterns:
            edge_cases += len(re.findall(pattern, test_code, re.IGNORECASE))

        return edge_cases

    def _categorize_tests(self, test_code: str) -> Dict[str, int]:
        """Categorize tests into unit and integration"""
        # Updated regex for Jest/TypeScript syntax
        unit_tests = len(re.findall(r'it\s*\(', test_code))  # All 'it' blocks are unit tests
        integration_tests = len(re.findall(r'describe\(.*integration|describe\(.*e2e', test_code, re.IGNORECASE))
        log_info(__name__, f"Test categorization - unit matches: {unit_tests}, integration matches: {integration_tests}, test_code preview: {test_code[:100]}")

        return {
            'unit': unit_tests,
            'integration': integration_tests
        }


class LangChainBestPracticesValidator:
    """Validates LangChain best practices in generated code"""

    def __init__(self):
        self.monitor = structured_log(__name__)

    def validate_langchain_compliance(self, code: str) -> LangChainCompliance:
        """Validate LangChain best practices compliance"""

        compliance = LangChainCompliance()

        # Check LCEL usage
        compliance.lcel_usage = self._check_lcel_usage(code)

        # Analyze error handling
        compliance.error_handling_score = self._analyze_error_handling(code)

        # Analyze state management
        compliance.state_management_score = self._analyze_state_management(code)

        # Calculate composability
        compliance.composability_score = self._calculate_composability(code)

        # Check tool integration
        compliance.tool_integration_score = self._analyze_tool_integration(code)

        # Overall compliance score
        compliance.overall_compliance = (
            compliance.error_handling_score +
            compliance.state_management_score +
            compliance.composability_score +
            compliance.tool_integration_score
        )

        return compliance

    def _check_lcel_usage(self, code: str) -> bool:
        """Check for LangChain Expression Language usage"""
        lcel_patterns = [
            r'\.pipe\(',
            r'RunnableSequence',
            r'RunnableParallel',
            r'RunnableLambda',
            r'\|.*\|',  # Pipe operator usage
        ]

        return any(re.search(pattern, code) for pattern in lcel_patterns)

    def _analyze_error_handling(self, code: str) -> float:
        """Analyze error handling patterns (0-10 scale)"""
        score = 0.0

        # Check for try-catch blocks
        try_catch_count = len(re.findall(r'try\s*\{', code))
        if try_catch_count > 0:
            score += try_catch_count * 3.0  # More generous scoring

        # Check for error handling patterns
        error_patterns = [
            r'catch\s*\(',
            r'except\s+',
            r'error',
            r'Error\(',
            r'throw\s+',
            r'raise\s+'
        ]

        error_handling_found = sum(1 for pattern in error_patterns if re.search(pattern, code))
        score += error_handling_found * 0.8  # More generous

        # Check for circuit breaker patterns
        if re.search(r'circuit.?breaker', code, re.IGNORECASE):
            score += 2.0

        return min(10.0, score)

    def _analyze_state_management(self, code: str) -> float:
        """Analyze state management patterns (0-10 scale)"""
        score = 0.0

        # Check for state classes
        if re.search(r'class.*State', code):
            score += 3.0

        # Check for immutable patterns
        immutable_patterns = [
            r'@dataclass',
            r'frozen\s*=\s*True',
            r'NamedTuple',
            r'ReadOnly',
            r'immutable'
        ]

        immutable_found = sum(1 for pattern in immutable_patterns if re.search(pattern, code, re.IGNORECASE))
        score += min(3.0, immutable_found * 1.5)

        # Check for proper state transformations
        transform_patterns = [
            r'with_',
            r'transform',
            r'update',
            r'merge',
            r'combine'
        ]

        transforms_found = sum(1 for pattern in transform_patterns if re.search(pattern, code, re.IGNORECASE))
        score += min(4.0, transforms_found * 1.0)

        return min(10.0, score)

    def _calculate_composability(self, code: str) -> float:
        """Calculate composability score (0-10 scale)"""
        score = 0.0

        # Check for functional composition patterns
        composition_patterns = [
            r'Runnable',
            r'Chain',
            r'compose',
            r'pipeline',
            r'workflow'
        ]

        composition_found = sum(1 for pattern in composition_patterns if re.search(pattern, code, re.IGNORECASE))
        score += min(5.0, composition_found * 2.0)  # More generous

        # Check for modular design
        modular_patterns = [
            r'interface',
            r'abstract\s+class',
            r'extends',
            r'implements',
            r'class'  # Add class pattern
        ]

        modular_found = sum(1 for pattern in modular_patterns if re.search(pattern, code))
        score += min(5.0, modular_found * 1.5)  # More generous

        print(f"DEBUG: Composability score: {score}, composition_found: {composition_found}, modular_found: {modular_found}")
        return min(10.0, score)

    def _analyze_tool_integration(self, code: str) -> float:
        """Analyze tool integration patterns (0-10 scale)"""
        score = 0.0

        # Check for tool-related patterns
        tool_patterns = [
            r'tool',
            r'Tool',
            r'bind_tools',
            r'with_types',
            r'StructuredTool',
            r'Toolkit'
        ]

        tools_found = sum(1 for pattern in tool_patterns if re.search(pattern, code))
        score += min(6.0, tools_found * 2.5)  # More generous

        # Check for proper tool error handling
        if re.search(r'tool.*error|error.*tool', code, re.IGNORECASE):
            score += 2.0

        # Check for tool validation
        if re.search(r'validate.*tool|tool.*validate', code, re.IGNORECASE):
            score += 2.0

        print(f"DEBUG: Tool integration score: {score}, tools_found: {tools_found}")
        return min(10.0, score)


class TestSuiteReporter:
    """Generates detailed reports for test suite validation results"""

    def __init__(self):
        self.monitor = structured_log(__name__)

    def generate_comprehensive_report(
        self,
        code: str,
        tests: str,
        validation_result: SuiteValidationResult,
        code_validator_report: ValidationReport = None
    ) -> str:
        """Generate a comprehensive markdown report"""

        report_sections = []

        # Header
        report_sections.append(self._generate_header(validation_result))

        # Code Validator Integration
        if code_validator_report:
            report_sections.append(self._generate_code_validator_section(code_validator_report))

        # Execution Results
        report_sections.append(self._generate_execution_section(validation_result))

        # Relationship Analysis
        report_sections.append(self._generate_relationship_section(validation_result))

        # LangChain Compliance
        report_sections.append(self._generate_compliance_section(validation_result))

        # Recommendations
        report_sections.append(self._generate_recommendations_section(validation_result))

        # Code Samples
        report_sections.append(self._generate_code_samples(code, tests))

        return '\n'.join(report_sections)

    def _generate_header(self, result: SuiteValidationResult) -> str:
        """Generate report header"""
        return f"""# Comprehensive Test Suite Validation Report

**Generated:** {result.timestamp}
**Code Hash:** {result.code_hash}
**Test Hash:** {result.test_hash}
**Overall Score:** {result.overall_score:.1f}/100
**Risk Level:** {result.risk_level.value.upper()}

## Executive Summary

This report provides a comprehensive analysis of LLM-generated TypeScript code and its corresponding tests. The validation assesses code execution, test effectiveness, test-code relationships, and LangChain best practices compliance.

"""

    def _generate_code_validator_section(self, report: ValidationReport) -> str:
        """Generate code validator integration section"""
        return f"""## Code Validator Integration

The generated code and tests were validated using the LLM Code Validation Framework:

- **Validation Score:** {report.overall_score:.1f}/100
- **Risk Level:** {report.risk_level.value.upper()}
- **Safety Check:** {"✅ Passed" if report.safety_check and report.safety_check.success else "❌ Failed"}
- **Test Results:** {"✅ Passed" if report.test_results and report.test_results.passed else "❌ Failed"}
- **Pattern Validation:** {"✅ Performed" if report.pattern_validation else "❌ Not performed"}

"""

    def _generate_execution_section(self, result: SuiteValidationResult) -> str:
        """Generate execution results section"""
        total_tests = result.test_execution.total_tests
        passed_tests = result.test_execution.passed_tests
        log_info(__name__, f"Generating execution section - total_tests: {total_tests}, passed: {passed_tests}")
        pass_percentage = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0
        log_info(__name__, f"Pass percentage: {pass_percentage}")
        return f"""## Execution Results

### Code Execution
- **Status:** {"✅ Successful" if result.code_execution.success else "❌ Failed"}
- **Execution Time:** {result.code_execution.execution_time:.2f}s
- **Output Lines:** {result.code_execution.output_lines}
- **Errors:** {result.code_execution.error_count}
- **Memory Usage:** {result.code_execution.memory_usage}MB
- **Timeout:** {"Yes" if result.code_execution.timeout_occurred else "No"}

### Test Execution
- **Total Tests:** {result.test_execution.total_tests}
- **Passed:** {result.test_execution.passed_tests} ({pass_percentage:.1f}%)
- **Failed:** {result.test_execution.failed_tests}
- **Skipped:** {result.test_execution.skipped_tests}
- **Coverage:** {result.test_execution.coverage_percentage:.1f}%
- **Execution Time:** {result.test_execution.execution_time:.2f}s

"""

    def _generate_relationship_section(self, result: SuiteValidationResult) -> str:
        """Generate test-code relationship section"""
        return f"""## Test-Code Relationship Analysis

- **Test Coverage:** {result.test_code_relationship.test_coverage:.1f}%
- **Assertion Quality:** {result.test_code_relationship.assertion_quality:.1f}/10
- **Mock Usage:** {"Yes" if result.test_code_relationship.mock_usage else "No"}
- **Edge Cases Covered:** {result.test_code_relationship.edge_case_coverage}
- **Integration Tests:** {result.test_code_relationship.integration_test_count}
- **Unit Tests:** {result.test_code_relationship.unit_test_count}

"""

    def _generate_compliance_section(self, result: SuiteValidationResult) -> str:
        """Generate LangChain compliance section"""
        return f"""## LangChain Best Practices Compliance

- **LCEL Usage:** {"✅ Detected" if result.langchain_compliance.lcel_usage else "❌ Not detected"}
- **Error Handling Score:** {result.langchain_compliance.error_handling_score:.1f}/10
- **State Management Score:** {result.langchain_compliance.state_management_score:.1f}/10
- **Composability Score:** {result.langchain_compliance.composability_score:.1f}/10
- **Tool Integration Score:** {result.langchain_compliance.tool_integration_score:.1f}/10
- **Overall Compliance:** {result.langchain_compliance.overall_compliance:.1f}/10

"""

    def _generate_recommendations_section(self, result: SuiteValidationResult) -> str:
        """Generate recommendations section"""
        sections = ["## Recommendations\n"]

        if result.critical_issues:
            sections.append("### Critical Issues")
            sections.extend(f"- {issue}" for issue in result.critical_issues)
            sections.append("")

        if result.warnings:
            sections.append("### Warnings")
            sections.extend(f"- {warning}" for warning in result.warnings)
            sections.append("")

        if result.suggestions:
            sections.append("### Suggestions")
            sections.extend(f"- {suggestion}" for suggestion in result.suggestions)
            sections.append("")

        return '\n'.join(sections)

    def _generate_code_samples(self, code: str, tests: str) -> str:
        """Generate code samples section"""
        return f"""## Code Samples

### Generated Code
```typescript
{code[:1000]}{"..." if len(code) > 1000 else ""}
```

### Generated Tests
```typescript
{tests[:1000]}{"..." if len(tests) > 1000 else ""}
```

"""


class LLMTestSuiteValidator:
    """Main test suite validation orchestrator"""

    def __init__(self):
        self.monitor = structured_log(__name__)
        self.executor = TestSuiteExecutor()
        self.test_validator = TestSuiteValidator()
        self.langchain_validator = LangChainBestPracticesValidator()
        self.reporter = TestSuiteReporter()

    def validate_test_suite(
        self,
        code: str,
        tests: str,
        context: Dict[str, Any] = None,
        include_code_validator: bool = True
    ) -> SuiteValidationResult:
        """Run complete test suite validation"""

        context = context or {}
        code_hash = self._generate_hash(code)
        test_hash = self._generate_hash(tests)

        result = SuiteValidationResult(
            code_hash=code_hash,
            test_hash=test_hash
        )

        # Phase 1: Execute code and tests
        try:
            self.monitor.info("Executing generated code and tests")
            result.code_execution, result.test_execution = self.executor.execute_code_and_tests(
                code, tests, context
            )
        except Exception as e:
            self.monitor.error(f"Execution phase failed: {str(e)}")
            result.critical_issues.append(f"Execution failed: {str(e)}")

        # Phase 2: Validate test-code relationship
        try:
            self.monitor.info("Analyzing test-code relationship")
            result.test_code_relationship = self.test_validator.validate_test_code_relationship(
                tests, code, result.test_execution
            )
        except Exception as e:
            self.monitor.error(f"Relationship validation failed: {str(e)}")
            result.critical_issues.append(f"Relationship validation failed: {str(e)}")

        # Phase 3: Validate LangChain compliance
        try:
            self.monitor.info("Validating LangChain best practices")
            result.langchain_compliance = self.langchain_validator.validate_langchain_compliance(code)
        except Exception as e:
            self.monitor.error(f"Compliance validation failed: {str(e)}")
            result.critical_issues.append(f"Compliance validation failed: {str(e)}")

        # Phase 4: Integrate with code validator framework
        code_validator_report = None
        if include_code_validator:
            try:
                self.monitor.info("Running code validator integration")
                code_validator_report = validate_generated_code(code, tests, context)
            except Exception as e:
                self.monitor.error(f"Code validator integration failed: {str(e)}")
                result.critical_issues.append(f"Code validator integration failed: {str(e)}")

        # Phase 5: Calculate overall score and risk
        result.overall_score = self._calculate_overall_score(result, code_validator_report)
        result.risk_level = self._assess_risk_level(result.overall_score)

        # Phase 6: Generate recommendations
        self._generate_recommendations(result, code_validator_report)

        return result

    def generate_detailed_report(
        self,
        code: str,
        tests: str,
        validation_result: SuiteValidationResult,
        code_validator_report: ValidationReport = None
    ) -> str:
        """Generate detailed markdown report"""
        return self.reporter.generate_comprehensive_report(
            code, tests, validation_result, code_validator_report
        )

    def _generate_hash(self, content: str) -> str:
        """Generate hash for content"""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()[:8]

    def _calculate_overall_score(
        self,
        result: SuiteValidationResult,
        code_validator_report: ValidationReport = None
    ) -> float:
        """Calculate overall test suite score"""

        # Base scores from different components
        execution_score = self._score_execution_results(result)
        relationship_score = self._score_relationship(result)
        compliance_score = result.langchain_compliance.overall_compliance * 10

        # Weighted average
        weights = {
            'execution': 0.4,
            'relationship': 0.3,
            'compliance': 0.3
        }

        score = (
            execution_score * weights['execution'] +
            relationship_score * weights['relationship'] +
            compliance_score * weights['compliance']
        )

        # Bonus from code validator
        if code_validator_report:
            score = (score + code_validator_report.overall_score) / 2

        return min(100.0, max(0.0, score))

    def _score_execution_results(self, result: SuiteValidationResult) -> float:
        """Score execution results (0-100)"""
        score = 0.0
        log_info(__name__, f"Scoring execution - total_tests: {result.test_execution.total_tests}, passed: {result.test_execution.passed_tests}")

        # Code execution success
        if result.code_execution.success:
            score += 40.0

        # Test execution success
        if result.test_execution.total_tests > 0:
            pass_rate = result.test_execution.passed_tests / result.test_execution.total_tests
            score += pass_rate * 40.0
            log_info(__name__, f"Pass rate: {pass_rate}, score addition: {pass_rate * 40.0}")
        else:
            log_info(__name__, "No tests executed, skipping pass rate calculation")

        # Coverage bonus
        score += min(20.0, result.test_execution.coverage_percentage / 5.0)

        log_info(__name__, f"Execution score: {score}")
        return score

    def _score_relationship(self, result: SuiteValidationResult) -> float:
        """Score test-code relationship (0-100)"""
        score = 0.0

        # Coverage contribution
        score += min(40.0, result.test_code_relationship.test_coverage)

        # Assertion quality
        score += result.test_code_relationship.assertion_quality * 2.0

        # Edge cases
        score += min(20.0, result.test_code_relationship.edge_case_coverage * 2.0)

        # Mock usage bonus
        if result.test_code_relationship.mock_usage:
            score += 10.0

        return score

    def _assess_risk_level(self, score: float) -> SuiteRiskLevel:
        """Assess risk level based on score"""
        if score >= 80:
            return SuiteRiskLevel.LOW
        elif score >= 60:
            return SuiteRiskLevel.MEDIUM
        elif score >= 40:
            return SuiteRiskLevel.HIGH
        else:
            return SuiteRiskLevel.CRITICAL

    def _generate_recommendations(
        self,
        result: SuiteValidationResult,
        code_validator_report: ValidationReport = None
    ):
        """Generate recommendations based on validation results"""

        # Critical issues
        if not result.code_execution.success:
            result.critical_issues.append("Generated code execution failed - review syntax and dependencies")

        if result.test_execution.failed_tests > 0:
            result.critical_issues.append(f"{result.test_execution.failed_tests} tests failed - fix test logic")

        if result.test_execution.coverage_percentage < 50:
            result.critical_issues.append("Test coverage below 50% - add more comprehensive tests")

        # Warnings
        if not result.test_code_relationship.mock_usage:
            result.warnings.append("No mock usage detected - consider adding mocks for external dependencies")

        if result.test_code_relationship.edge_case_coverage < 3:
            result.warnings.append("Limited edge case coverage - add tests for boundary conditions")

        if result.langchain_compliance.overall_compliance < 5.0:
            result.warnings.append("Low LangChain best practices compliance - review patterns")

        # Suggestions
        if result.test_code_relationship.assertion_quality < 5.0:
            result.suggestions.append("Improve assertion quality with more diverse test assertions")

        if not result.langchain_compliance.lcel_usage:
            result.suggestions.append("Consider using LangChain Expression Language (LCEL) for better composability")

        if result.langchain_compliance.error_handling_score < 5.0:
            result.suggestions.append("Enhance error handling patterns with try-catch blocks and circuit breakers")


# Global instance
test_suite_validator = LLMTestSuiteValidator()

def validate_llm_test_suite(
    code: str,
    tests: str,
    context: Dict[str, Any] = None,
    include_code_validator: bool = True
) -> Tuple[SuiteValidationResult, str]:
    """Global function for test suite validation"""
    # Run validation
    result = test_suite_validator.validate_test_suite(code, tests, context, include_code_validator)

    # Get code validator report if needed for report generation
    code_validator_report = None
    if include_code_validator:
        try:
            code_validator_report = validate_generated_code(code, tests, context)
        except Exception:
            pass  # Report generation will handle None gracefully

    report = generate_test_suite_report(code, tests, result, code_validator_report)
    return result, report

def generate_test_suite_report(
    code: str,
    tests: str,
    validation_result: SuiteValidationResult,
    code_validator_report: ValidationReport = None
) -> str:
    """Global function for generating detailed reports"""
    return test_suite_validator.generate_detailed_report(
        code, tests, validation_result, code_validator_report
    )
