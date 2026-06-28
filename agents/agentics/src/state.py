from typing import TypedDict, List, Dict, Any


class State(TypedDict, total=False):
    # Core workflow fields
    url: str
    ticket_content: str
    refined_ticket: dict
    result: dict

    # Generated outputs
    generated_code: str
    generated_tests: str
    method_name: str
    command_id: str

    # File context
    relevant_code_files: List[Dict[str, str]]
    relevant_test_files: List[Dict[str, str]]

    # Test metrics
    existing_tests_passed: int
    post_integration_tests_passed: int
    tests_passed: bool

    # Validation & recovery
    validation_score: int
    recovery_attempt: int

    # Errors
    error: str
    error_type: str
    success: bool

    # Eval loop
    eval_scores: dict
    eval_passed: bool
    eval_reasons: List[str]
    failed_criteria: List[str]

    # Regression testing
    regression_check: dict

    # Integration gate
    integrated: bool
    integration_blocked_reason: str
    eval_failure_context: str

    # Internal: persisted across routing retries
    _persisted_gen_code: str
    _gen_attempt: int
    _test_attempt: int
    _is_eval_retry_active: bool
    _error_ctx: str
    _retry_prompt: str
    _integrated_into_main: bool
    _project_root: str
    _persisted_slug: str
    _persisted_export_name: str
    _persisted_command_id: str