import pytest
from typing import get_type_hints
from src.state import State

def test_state_is_typed_dict():
    # Given: State class
    # When: Checking its type

    # Then: State is a TypedDict
    assert hasattr(State, '__annotations__')

def test_state_keys():
    # Given: Expected keys for State
    expected_keys = {
        'url', 'ticket_content', 'refined_ticket', 'result', 'generated_code',
        'generated_tests', 'existing_tests_passed', 'existing_coverage_all_files',
        'relevant_code_files', 'relevant_test_files', 'available_dependencies',
        'post_integration_tests_passed', 'post_integration_coverage_all_files',
        'coverage_improvement', 'tests_improvement', 'feedback_metrics',
        'conversation_history', 'memory', 'feedback'
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
        relevant_test_files=[]
    )

    # Then: State is a dict with correct values
    assert isinstance(state, dict)
    assert state['url'] == "https://example.com"

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
        relevant_test_files=[]
    )

    # When: Adding optional key
    state['available_dependencies'] = []

    # Then: Key is present
    assert 'available_dependencies' in state
