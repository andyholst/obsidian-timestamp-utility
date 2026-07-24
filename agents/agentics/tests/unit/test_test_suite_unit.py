"""Real unit test for the ``test_suite`` module (replaces scripts/test_suite_validation.py).

Exercises the real ``validate_llm_test_suite`` + ``generate_test_suite_report`` against a
small but realistic TS fixture loaded from this file (no inline hardcoded fake example that
hides regressions). Mocks ONLY external boundaries (none here — pure logic).
"""
import os
import sys

import pytest

# Make the package importable when run via docker compose (mounted at /app/prod)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.test_suite import (  # noqa: E402
    validate_llm_test_suite,
    generate_test_suite_report,
    ValidationResult,
)

REAL_CODE = """
export class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }
}
"""

REAL_TESTS = """
describe('Calculator', () => {
    it('should add numbers', () => {
        const calc = new Calculator();
        expect(calc.add(2, 3)).toBe(5);
    });
});
"""


def test_validate_llm_test_suite_returns_result():
    result, report = validate_llm_test_suite(
        REAL_CODE, REAL_TESTS, include_code_validator=False, skip_execution=True
    )
    assert isinstance(result, ValidationResult)
    # Real attributes the pipeline relies on
    for attr in (
        "overall_score",
        "risk_level",
        "code_execution",
        "test_execution",
        "test_code_relationship",
        "langchain_compliance",
    ):
        assert hasattr(result, attr), f"missing attribute {attr}"


def test_generate_test_suite_report_is_non_trivial():
    result, _ = validate_llm_test_suite(
        REAL_CODE, REAL_TESTS, include_code_validator=False
    )
    report = generate_test_suite_report(REAL_CODE, REAL_TESTS, result)
    assert isinstance(report, str)
    assert len(report) > 100


def test_validate_handles_empty_input_gracefully():
    # Real behaviour on degenerate input must not raise unexpectedly
    result, report = validate_llm_test_suite("", "", include_code_validator=False)
    assert isinstance(result, ValidationResult)
    assert isinstance(report, str)
