import pytest
from typing import get_type_hints
from src.state import State


def test_state_is_typed_dict():
    # Given: State class
    # When: Checking its type

    # Then: State is a TypedDict
    assert hasattr(State, "__annotations__")


def test_state_keys():
    # Given: Expected keys for State
    expected_keys = {
        "url",
        "ticket_content",
        "refined_ticket",
        "result",
        "generated_code",
        "generated_tests",
        "method_name",
        "command_id",
        "relevant_code_files",
        "relevant_test_files",
        "existing_tests_passed",
        "post_integration_tests_passed",
        "validation_score",
        "recovery_attempt",
        "error",
        "error_type",
        "success",
        "eval_scores",
        "eval_passed",
        "eval_reasons",
        "failed_criteria",
        "regression_check",
        "integrated",
        "integration_blocked_reason",
        "eval_failure_context",
        "tests_passed",
        # Internal: persisted across routing retries
        "_persisted_gen_code",
        "_gen_attempt",
        "_test_attempt",
        "_is_eval_retry_active",
        "_error_ctx",
        "_retry_prompt",
        "_integrated_into_main",
        "_project_root",
    }

    # When: Getting type hints
    hints = get_type_hints(State)

    # Then: Keys match expected
    assert set(hints.keys()) == expected_keys


def test_state_instantiation():
    # Given: State parameters
    # When: Instantiating State
    state = State(
        url="https://example.com",
        ticket_content="content",
        refined_ticket={},
        result={},
        generated_code="",
        generated_tests="",
        existing_tests_passed=0,
        existing_coverage_all_files=0.0,
        relevant_code_files=[],
        relevant_test_files=[],
    )

    # Then: State is a dict with correct values
    assert isinstance(state, dict)
    assert state["url"] == "https://example.com"


def test_state_optional_keys():
    # Given: A State instance
    state = State(
        url="",
        ticket_content="",
        refined_ticket={},
        result={},
        generated_code="",
        generated_tests="",
        existing_tests_passed=0,
        existing_coverage_all_files=0.0,
        relevant_code_files=[],
        relevant_test_files=[],
    )

    # When: Adding optional key
    state["available_dependencies"] = []

    # Then: Key is present
    assert "available_dependencies" in state


def test_state_tests_passed_key():
    """State should accept the tests_passed boolean key."""
    state = State(
        url="",
        ticket_content="",
        refined_ticket={},
        result={},
        generated_code="",
        generated_tests="",
        existing_tests_passed=0,
        existing_coverage_all_files=0.0,
        relevant_code_files=[],
        relevant_test_files=[],
    )
    state["tests_passed"] = True
    assert state["tests_passed"] is True
    state["tests_passed"] = False
    assert state["tests_passed"] is False


def test_state_eval_failure_context_key():
    """State should accept the eval_failure_context string key."""
    state = State(
        url="",
        ticket_content="",
        refined_ticket={},
        result={},
        generated_code="",
        generated_tests="",
        existing_tests_passed=0,
        existing_coverage_all_files=0.0,
        relevant_code_files=[],
        relevant_test_files=[],
    )
    ctx = "Score: 0.45/1.0. Failed criteria: has_actionable_output. What was wrong: has_actionable_output=0.00."
    state["eval_failure_context"] = ctx
    assert state["eval_failure_context"] == ctx


def test_state_integrated_key():
    """State should accept the integrated boolean key."""
    state = State(
        url="",
        ticket_content="",
        refined_ticket={},
        result={},
        generated_code="",
        generated_tests="",
        existing_tests_passed=0,
        existing_coverage_all_files=0.0,
        relevant_code_files=[],
        relevant_test_files=[],
    )
    state["integrated"] = True
    assert state["integrated"] is True


def test_state_integration_blocked_reason_key():
    """State should accept the integration_blocked_reason string key."""
    state = State(
        url="",
        ticket_content="",
        refined_ticket={},
        result={},
        generated_code="",
        generated_tests="",
        existing_tests_passed=0,
        existing_coverage_all_files=0.0,
        relevant_code_files=[],
        relevant_test_files=[],
    )
    state["integration_blocked_reason"] = "Score too low"
    assert state["integration_blocked_reason"] == "Score too low"


def test_state_eval_fields():
    """State eval-related fields (eval_scores, eval_passed, eval_reasons, failed_criteria)."""
    state = State(
        url="",
        ticket_content="",
        refined_ticket={},
        result={},
        generated_code="",
        generated_tests="",
        existing_tests_passed=0,
        existing_coverage_all_files=0.0,
        relevant_code_files=[],
        relevant_test_files=[],
    )
    state["eval_scores"] = {"has_actionable_output": 0.9}
    state["eval_passed"] = True
    state["eval_reasons"] = ["ok"]
    state["failed_criteria"] = []
    assert state["eval_scores"] == {"has_actionable_output": 0.9}
    assert state["eval_passed"] is True
    assert state["eval_reasons"] == ["ok"]
    assert state["failed_criteria"] == []


def test_state_regression_check_key():
    """State should accept the regression_check dict key."""
    state = State(
        url="",
        ticket_content="",
        refined_ticket={},
        result={},
        generated_code="",
        generated_tests="",
        existing_tests_passed=0,
        existing_coverage_all_files=0.0,
        relevant_code_files=[],
        relevant_test_files=[],
    )
    state["regression_check"] = {"regressed": False, "deltas": {}}
    assert state["regression_check"]["regressed"] is False
