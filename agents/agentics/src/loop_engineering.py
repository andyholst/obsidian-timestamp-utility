"""
Loop Engineering — Reusable verify-and-retry infrastructure for LangGraph agent nodes.

Implements the closed-loop protocol from VERIFICATION.md:
  EXECUTE → VERIFY → PASS / FAIL → retry with error feedback → EXHAUST → recovery

Designed for the State TypedDict architecture (workflow.py / state.py).
"""

import os
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration (env-driven, per VERIFICATION.md)
# ---------------------------------------------------------------------------

AGENT_MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "3"))
AGENT_RETRY_THRESHOLD = float(os.getenv("AGENT_RETRY_THRESHOLD", "80"))
AGENT_VERIFY_ENABLED = os.getenv("AGENT_VERIFY_ENABLED", "true").lower() in ("true", "1", "yes")
AGENT_FAST_MODE = os.getenv("AGENT_FAST_MODE", "false").lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Verification Result
# ---------------------------------------------------------------------------

class VerificationResult:
    """Standard output from any node verification step."""

    def __init__(
        self,
        passed: bool,
        score: float = 0.0,
        errors: Optional[List[Dict[str, str]]] = None,
        warnings: Optional[List[str]] = None,
        retry_prompt: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.passed = passed
        self.score = score
        self.errors = errors or []
        self.warnings = warnings or []
        self.retry_prompt = retry_prompt
        self.metadata = metadata or {}

    def __repr__(self):
        return f"VerificationResult(passed={self.passed}, score={self.score:.1f}, errors={len(self.errors)})"


# ---------------------------------------------------------------------------
# Core: verify_and_retry
# ---------------------------------------------------------------------------

def verify_and_retry(
    node_name: str,
    max_attempts: int,
    execute_fn: Callable[[Dict], Dict],
    verify_fn: Callable[[Dict], VerificationResult],
    state: Dict,
    attempt_counter_key: str = "recovery_attempt",
) -> Tuple[Dict, VerificationResult]:
    """
    Execute a node, verify its output, and retry with error feedback on failure.

    Replaces inline `for attempt in range(N):` loops throughout the workflow.

    Args:
        node_name: Graph node name (used for logging).
        max_attempts: Max retry attempts (try N times total).
        execute_fn: The node's core logic: state -> state.
        verify_fn: Verification function: state -> VerificationResult.
        state: Current State dict.
        attempt_counter_key: Key in state for attempt counter.

    Returns:
        Tuple of (final_state, verification_result).
    """
    if not AGENT_VERIFY_ENABLED or AGENT_FAST_MODE:
        state = execute_fn(state)
        return state, VerificationResult(passed=True, score=100.0, metadata={"mode": "fast"})

    current_state = dict(state)
    result = VerificationResult(passed=False, score=0.0)

    for attempt in range(max_attempts):
        logger.info(f"[{node_name}] Attempt {attempt + 1}/{max_attempts}")

        # EXECUTE
        try:
            current_state = execute_fn(current_state)
        except Exception as e:
            logger.error(f"[{node_name}] Execution error (attempt {attempt + 1}): {e}")
            current_state[attempt_counter_key] = current_state.get(attempt_counter_key, 0) + 1
            current_state["error"] = str(e)
            current_state["error_type"] = type(e).__name__
            result = VerificationResult(
                passed=False,
                score=0.0,
                errors=[{"type": "execution_error", "message": str(e)}],
                retry_prompt=f"Execution failed: {e}. Please try again.",
            )
            continue

        # VERIFY
        try:
            result = verify_fn(current_state)
        except Exception as e:
            logger.error(f"[{node_name}] Verification error (attempt {attempt + 1}): {e}")
            result = VerificationResult(
                passed=False,
                score=0.0,
                errors=[{"type": "verify_error", "message": str(e)}],
            )

        # PASS → done
        if result.passed and result.score >= AGENT_RETRY_THRESHOLD:
            logger.info(f"[{node_name}] PASSED on attempt {attempt + 1} (score={result.score:.1f})")
            result.metadata["total_attempts"] = attempt + 1
            return current_state, result

        # FAIL → prepare retry feedback
        logger.info(
            f"[{node_name}] FAILED on attempt {attempt + 1} "
            f"(score={result.score:.1f}, errors={len(result.errors)})"
        )
        current_state[attempt_counter_key] = current_state.get(attempt_counter_key, 0) + 1
        current_state["validation_score"] = int(result.score)

        # Inject retry prompt into state for next LLM call
        if result.retry_prompt:
            current_state["_retry_prompt"] = result.retry_prompt
            current_state["_error_ctx"] = "; ".join(e.get("message", "") for e in result.errors)

    # EXHAUSTED
    logger.warning(
        f"[{node_name}] EXHAUSTED after {max_attempts} attempts (final score={result.score:.1f})"
    )
    result.metadata["total_attempts"] = max_attempts
    return current_state, result


# ---------------------------------------------------------------------------
# Verification functions per node
# ---------------------------------------------------------------------------

def verify_generated_code(state: Dict) -> VerificationResult:
    """Verify that generated code meets structural requirements and compiles."""
    import subprocess
    import tempfile
    import os
    errors = []
    gen_code = state.get("generated_code", "")

    if not gen_code or not gen_code.strip():
        errors.append({"type": "empty_code", "message": "No code was generated"})
    elif len(gen_code.strip()) < 20:
        errors.append({"type": "too_short", "message": "Generated code is too short to be valid"})
    else:
        # Verify the code actually compiles with tsc
        project_root = state.get("_project_root", "")
        if project_root and os.path.isdir(project_root):
            try:
                # Write to temp file and type-check
                with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False, dir=project_root) as f:
                    f.write(gen_code)
                    tmp_path = f.name
                result = subprocess.run(
                    ["./node_modules/.bin/tsc", "--noEmit", "--skipLibCheck", "--target", "es2018", tmp_path],
                    cwd=project_root, capture_output=True, text=True, timeout=30
                )
                os.unlink(tmp_path)
                if result.returncode != 0:
                    # Extract first error
                    err_lines = [l for l in result.stderr.split('\n') if l.strip() and 'error' in l.lower()]
                    first_err = err_lines[0][:200] if err_lines else result.stderr[:200]
                    errors.append({"type": "compile_error", "message": f"TypeScript compilation failed: {first_err}"})
            except Exception as e:
                # If tsc check fails (e.g., not installed), skip but log
                pass

    score = max(0.0, 100.0 - (len(errors) * 30.0))
    passed = len(errors) == 0

    retry_prompt = ""
    if not passed:
        retry_prompt = (
            "The generated code had issues:\n"
            + "\n".join(f"- {e['message']}" for e in errors)
            + "\n\nPlease regenerate the code fixing these issues. USE BROWSER-COMPATIBLE APIs ONLY (no Buffer, no require, no Node.js modules)."
        )

    return VerificationResult(passed=passed, score=score, errors=errors, retry_prompt=retry_prompt)


def verify_tests_passed(state: Dict) -> VerificationResult:
    """Verify that generated tests actually pass."""
    errors = []
    tests_passed = state.get("tests_passed", False)
    gen_test_code = state.get("generated_tests", "")

    if not gen_test_code:
        errors.append({"type": "no_tests", "message": "No tests were generated/written"})
    elif not tests_passed:
        errors.append({"type": "tests_failed", "message": "Tests exist but do not pass"})

    score = 100.0 if not errors else 0.0
    passed = not errors

    retry_prompt = ""
    if not passed:
        error_ctx = state.get("_error_ctx", "Unknown test failure")
        retry_prompt = (
            f"Tests failed with errors:\n{error_ctx}\n\n"
            "Please fix the code to pass all tests."
        )

    return VerificationResult(passed=passed, score=score, errors=errors, retry_prompt=retry_prompt)


def verify_eval_gate(state: Dict) -> VerificationResult:
    """Verify that the eval quality gate passed."""
    errors = []
    eval_passed = state.get("eval_passed", False)

    if not eval_passed:
        failed = state.get("failed_criteria", [])
        for criterion in failed:
            errors.append({"type": "eval_failed", "message": f"Eval criterion failed: {criterion}"})

    score = state.get("validation_score", 100 if eval_passed else 0)

    passed = len(errors) == 0
    retry_prompt = ""
    if not passed:
        failure_ctx = state.get("eval_failure_context", "Quality gate failed")
        retry_prompt = (
            f"Quality eval gate failed:\n{failure_ctx}\n\n"
            "Please regenerate with higher quality."
        )

    return VerificationResult(passed=passed, score=float(score), errors=errors, retry_prompt=retry_prompt)


# ---------------------------------------------------------------------------
# Graph edge helper
# ---------------------------------------------------------------------------

def make_verification_router(
    node_name: str,
    attempt_key: str = "recovery_attempt",
    max_retries: int = AGENT_MAX_RETRIES,
) -> Callable[[Dict], str]:
    """
    Create a LangGraph conditional edge function that routes based on verification.

    Usage:
        graph.add_conditional_edges(
            "generate_code_tests",
            make_verification_router("recovery_attempt"),
            {"pass": "test", "fail": "generate_code_tests"},
        )
    """

    def router(state: Dict) -> str:
        if not AGENT_VERIFY_ENABLED or AGENT_FAST_MODE:
            return "pass"

        attempt = state.get(attempt_key, 0)
        eval_passed = state.get("eval_passed", False)

        if eval_passed:
            return "pass"

        if attempt >= max_retries:
            return "pass"  # Exhausted, let downstream handle

        return "fail"

    return router
