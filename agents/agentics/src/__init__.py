"""Agentics package — quality-gated TypeScript code generation for Obsidian plugins."""

from .state import State
from .eval_rubric import score_output, gate_check, record_failure, RegressionTracker, RubricStore
from .test_suite import GoldStandardSuite
from .production_monitor import run_production_check, close_the_loop, ThresholdAlerter
from .loop_engineering import (
    verify_and_retry,
    VerificationResult,
    make_verification_router,
    verify_generated_code,
    verify_tests_passed,
    verify_eval_gate,
    AGENT_MAX_RETRIES,
    AGENT_RETRY_THRESHOLD,
    AGENT_VERIFY_ENABLED,
    AGENT_FAST_MODE,
)
