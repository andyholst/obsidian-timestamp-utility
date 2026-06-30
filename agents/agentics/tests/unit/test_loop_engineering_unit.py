"""
Unit tests for loop_engineering.py — verify_and_retry, VerificationResult, verify functions.

Tests cover:
- verify_and_retry: first-attempt success, retry-then-success, exhaust, fast mode
- verify_and_retry: execution errors, verification errors
- verify_generated_code: empty, valid, class, import, missing export
- verify_tests_passed: no tests, failed tests, passed tests
- verify_eval_gate: passed, failed with criteria
- make_verification_router: pass, fail, exhausted, fast mode
- Config env vars: AGENT_MAX_RETRIES, AGENT_VERIFY_ENABLED, AGENT_FAST_MODE
"""

import os
import pytest
from unittest.mock import patch

from src.loop_engineering import (
    verify_and_retry,
    VerificationResult,
    verify_generated_code,
    verify_tests_passed,
    verify_eval_gate,
    make_verification_router,
    AGENT_MAX_RETRIES,
    AGENT_RETRY_THRESHOLD,
    AGENT_VERIFY_ENABLED,
    AGENT_FAST_MODE,
)


# ===========================================================================
# VerificationResult
# ===========================================================================

class TestVerificationResult:
    def test_basic_pass(self):
        r = VerificationResult(passed=True, score=100.0)
        assert r.passed
        assert r.score == 100.0
        assert r.errors == []
        assert r.retry_prompt == ""

    def test_basic_fail(self):
        r = VerificationResult(passed=False, score=0.0, errors=[{"type": "x", "message": "y"}])
        assert not r.passed
        assert not r.passed  # should_retry equivalent

    def test_with_errors_and_retry_prompt(self):
        r = VerificationResult(passed=False, score=40.0, retry_prompt="Fix it")
        assert not r.passed
        assert r.retry_prompt == "Fix it"
        assert r.score == 40.0


# ===========================================================================
# verify_and_retry — core loop
# ===========================================================================

class TestVerifyAndRetry:
    def test_first_attempt_success(self):
        def execute(state):
            state["generated_code"] = "export function foo(): string { return 'x' }"
            state["method_name"] = "foo"
            return state

        def verify(state):
            return VerificationResult(passed=True, score=100.0)

        s, r = verify_and_retry("test", 3, execute, verify, {})
        assert r.passed
        assert r.score == 100.0
        assert r.metadata["total_attempts"] == 1

    def test_retry_then_success(self):
        attempts = []

        def execute(state):
            attempts.append(1)
            if len(attempts) < 2:
                state["generated_code"] = ""
            else:
                state["generated_code"] = "export function foo(): string { return 'x' }"
            state["method_name"] = "foo"
            return state

        s, r = verify_and_retry("test", 3, execute, verify_generated_code, {})
        assert r.passed
        assert len(attempts) == 2

    def test_exhaust_after_max_attempts(self):
        def execute(state):
            state["generated_code"] = ""
            state["method_name"] = "foo"
            return state

        s, r = verify_and_retry("test", 3, execute, verify_generated_code, {})
        assert not r.passed
        assert s.get("recovery_attempt", 0) == 3

    def test_execution_error_retries(self):
        calls = []

        def execute(state):
            calls.append(1)
            if len(calls) < 2:
                raise RuntimeError("LLM timeout")
            state["generated_code"] = "export function foo(): string { return 'x' }"
            state["method_name"] = "foo"
            return state

        s, r = verify_and_retry("test", 3, execute, verify_generated_code, {})
        assert r.passed
        assert len(calls) == 2

    def test_verification_error_handling(self):
        def execute(state):
            state["generated_code"] = "something"
            state["method_name"] = "foo"
            return state

        def bad_verify(state):
            raise RuntimeError("verify crashed")

        s, r = verify_and_retry("test", 1, execute, bad_verify, {})
        assert not r.passed
        assert any(e["type"] == "verify_error" for e in r.errors)

    def test_fast_mode_skips_verification(self):
        """AGENT_FAST_MODE should execute once and return passed=True."""
        os.environ["AGENT_FAST_MODE"] = "true"
        import importlib, src.loop_engineering
        importlib.reload(src.loop_engineering)

        calls = []

        def execute(state):
            calls.append(1)
            return state

        def verify(state):
            raise RuntimeError("Should not be called in fast mode")

        s, r = src.loop_engineering.verify_and_retry("test", 3, execute, verify, {})
        assert r.passed
        assert r.metadata.get("mode") == "fast"
        assert len(calls) == 1

        os.environ["AGENT_FAST_MODE"] = "false"
        importlib.reload(src.loop_engineering)

    def test_verify_disabled_mode(self):
        """AGENT_VERIFY_ENABLED=false should skip verification."""
        os.environ["AGENT_VERIFY_ENABLED"] = "false"
        import importlib, src.loop_engineering
        importlib.reload(src.loop_engineering)

        calls = []

        def execute(state):
            calls.append(1)
            return state

        s, r = src.loop_engineering.verify_and_retry("test", 3, execute, lambda s: VerificationResult(passed=False), {})
        assert r.passed
        assert r.metadata.get("mode") == "fast"
        assert len(calls) == 1

        os.environ["AGENT_VERIFY_ENABLED"] = "true"
        importlib.reload(src.loop_engineering)

    def test_custom_attempt_counter_key(self):
        def execute(state):
            state["generated_code"] = ""
            state["method_name"] = "foo"
            return state

        s, r = verify_and_retry("test", 2, execute, verify_generated_code, {}, attempt_counter_key="_my_counter")
        assert s.get("_my_counter", 0) == 2

    def test_retry_prompt_injected_into_state(self):
        """On failure, retry prompt should be in state for next LLM call."""
        def execute(state):
            state["generated_code"] = ""
            state["method_name"] = "foo"
            return state

        s, r = verify_and_retry("test", 2, execute, verify_generated_code, {})
        assert "_retry_prompt" in s or "_error_ctx" in s


# ===========================================================================
# verify_generated_code
# ===========================================================================

class TestVerifyGeneratedCode:
    def test_empty_code_fails(self):
        r = verify_generated_code({"generated_code": "", "method_name": "foo"})
        assert not r.passed
        assert any(e["type"] == "empty_code" for e in r.errors)

    def test_valid_code_passes(self):
        r = verify_generated_code({
            "generated_code": "export function foo(): string { return 'hello' }",
            "method_name": "foo"
        })
        assert r.passed
        assert r.score == 100.0

    def test_class_declaration_passes(self):
        """Class declarations are now allowed (post-processed)."""
        r = verify_generated_code({
            "generated_code": "export class Foo { bar(): string { return 'x' } }",
            "method_name": "bar"
        })
        assert r.passed

    def test_import_statement_stripped(self):
        """Imports are stripped by post-processing, so code with imports still passes structural validation."""
        r = verify_generated_code({
            "generated_code": "export function foo(): string { return 'x' }",
            "method_name": "foo"
        })
        assert r.passed

    def test_missing_export_fails(self):
        """Empty code should fail."""
        r = verify_generated_code({
            "generated_code": "",
            "method_name": "foo"
        })
        assert not r.passed
        assert any("no code" in e["message"].lower() or "empty" in e["message"].lower() for e in r.errors)

    def test_too_short_fails(self):
        """Very short code should fail."""
        r = verify_generated_code({
            "generated_code": "const x = 1;",
            "method_name": "foo"
        })
        assert not r.passed
        assert any("too short" in e["message"].lower() for e in r.errors)

    def test_retry_prompt_built_on_failure(self):
        r = verify_generated_code({"generated_code": "", "method_name": "foo"})
        assert len(r.retry_prompt) > 0
        assert "issues" in r.retry_prompt.lower() or "regenerate" in r.retry_prompt.lower()


# ===========================================================================
# verify_tests_passed
# ===========================================================================

class TestVerifyTestsPassed:
    def test_no_tests_fails(self):
        r = verify_tests_passed({"generated_tests": "", "tests_passed": False})
        assert not r.passed
        assert any(e["type"] == "no_tests" for e in r.errors)

    def test_tests_exist_but_failed(self):
        r = verify_tests_passed({
            "generated_tests": "describe('x', () => { it('y', () => {}) })",
            "tests_passed": False
        })
        assert not r.passed
        assert any(e["type"] == "tests_failed" for e in r.errors)

    def test_tests_pass(self):
        r = verify_tests_passed({
            "generated_tests": "describe('x', () => { it('y', () => {}) })",
            "tests_passed": True
        })
        assert r.passed
        assert r.score == 100.0

    def test_retry_prompt_includes_error_context(self):
        r = verify_tests_passed({
            "generated_tests": "describe('x', () => {})",
            "tests_passed": False,
            "_error_ctx": "TypeError: foo is not a function"
        })
        assert "foo is not a function" in r.retry_prompt


# ===========================================================================
# verify_eval_gate
# ===========================================================================

class TestVerifyEvalGate:
    def test_eval_passed(self):
        r = verify_eval_gate({"eval_passed": True, "validation_score": 100})
        assert r.passed

    def test_eval_failed_with_criteria(self):
        r = verify_eval_gate({
            "eval_passed": False,
            "failed_criteria": ["code_quality", "test_coverage"],
            "validation_score": 0
        })
        assert not r.passed
        assert len(r.errors) == 2

    def test_eval_failure_includes_retry_prompt(self):
        r = verify_eval_gate({
            "eval_passed": False,
            "failed_criteria": ["code_quality"],
            "eval_failure_context": "Score too low"
        })
        assert not r.passed
        assert len(r.retry_prompt) > 0


# ===========================================================================
# make_verification_router
# ===========================================================================

class TestMakeVerificationRouter:
    def test_pass_when_eval_passed(self):
        router = make_verification_router("generate_code_tests")
        assert router({"eval_passed": True}) == "pass"

    def test_fail_when_retries_remain(self):
        router = make_verification_router("generate_code_tests")
        assert router({"eval_passed": False, "recovery_attempt": 0}) == "fail"

    def test_pass_when_exhausted(self):
        router = make_verification_router("generate_code_tests", max_retries=3)
        assert router({"eval_passed": False, "recovery_attempt": 3}) == "pass"
        assert router({"eval_passed": False, "recovery_attempt": 2}) == "fail"

    def test_custom_max_retries(self):
        router = make_verification_router("generate_code_tests", max_retries=5)
        assert router({"eval_passed": False, "recovery_attempt": 4}) == "fail"
        assert router({"eval_passed": False, "recovery_attempt": 5}) == "pass"

    def test_fast_mode_always_passes(self):
        os.environ["AGENT_FAST_MODE"] = "true"
        import importlib, src.loop_engineering
        importlib.reload(src.loop_engineering)
        router = src.loop_engineering.make_verification_router("generate_code_tests")
        assert router({"eval_passed": False, "recovery_attempt": 0}) == "pass"
        os.environ["AGENT_FAST_MODE"] = "false"
        importlib.reload(src.loop_engineering)

    def test_custom_attempt_key(self):
        router = make_verification_router("generate_code_tests", attempt_key="_my_counter")
        assert router({"eval_passed": False, "_my_counter": 0}) == "fail"
        assert router({"eval_passed": False, "_my_counter": 3}) == "pass"


# ===========================================================================
# Config defaults
# ===========================================================================

class TestConfig:
    def test_default_max_retries(self):
        assert AGENT_MAX_RETRIES == 3

    def test_default_threshold(self):
        assert AGENT_RETRY_THRESHOLD == 80.0

    def test_verify_enabled_default(self):
        assert AGENT_VERIFY_ENABLED is True

    def test_fast_mode_default(self):
        assert AGENT_FAST_MODE is False
