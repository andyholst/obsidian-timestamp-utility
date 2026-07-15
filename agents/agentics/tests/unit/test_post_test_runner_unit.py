"""Unit tests for PostTestRunnerAgent gates (agentic-self-correct-loop §2.3/§3.3/§4.4).

These assert REAL logic in PostTestRunnerAgent: the lint gate, the strict-growth test
gate, and the omission guard. External boundaries (the lint subprocess, the filesystem)
are mocked ONLY where unavoidable — the unit under test is never mocked. This satisfies
B18 (mock external only).
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.post_test_runner_agent import (  # noqa: E402
    PostTestRunnerAgent,
    MAX_SELF_CORRECT_ATTEMPTS,
)
from src.exceptions import LintError, TestRecoveryNeeded, OmissionDetected, CompileError  # noqa: E402


@pytest.fixture
def agent(tmp_path):
    """Build a PostTestRunnerAgent pointed at a temp project root (real logic, no LLM)."""
    env = {
        "PROJECT_ROOT": str(tmp_path),
        "INSTALL_COMMAND": "true",
        "TEST_COMMAND": "true",
    }
    with patch.dict(os.environ, env):
        a = PostTestRunnerAgent(llm=MagicMock())
        a.project_root = str(tmp_path)
        return a


def _mock_run(returncode, stdout="", stderr=""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# --- §2.3 Lint gate -----------------------------------------------------------
def test_lint_gate_returns_failure_string_on_eslint_error(agent, tmp_path):
    # A lint tool WITH a config present must run and return the failure string
    # when eslint exits non-zero. (post_test_runner skips tools with NO config,
    # so we must provide one here or the gate returns None.)
    import json
    with open(tmp_path / ".eslintrc.json", "w") as f:
        json.dump({"rules": {}}, f)
    with patch("subprocess.run", return_value=_mock_run(1, stderr="error: unused var")):
        result = agent.run_lint_gate()
    assert result is not None
    assert "[eslint]" in result


def _stub_tool_executor(a, test_output):
    """Mock the external boundary: tool_executor.execute_tool(key, ...) by tool name.

    process() drives npm/typecheck/test through self.tool_executor (not the module-level
    tool functions), so we patch THAT — the only true external boundary. Real logic in
    process() (lint gate, strict-growth, omission) is exercised un-mocked (B18).
    """
    def _exec(key, params=None):
        if key == "typescript_typecheck_tool":
            raise CompileError("typecheck skipped in test")
        if key == "npm_run_tool":
            return test_output
        if key == "npm_install_tool":
            return "Successfully installed"
        if key == "check_file_exists_tool":
            return True
        return None
    a.tool_executor.execute_tool = MagicMock(side_effect=_exec)


def test_lint_gate_raises_linterror_in_process(agent):
    # process() must raise LintError when the lint gate fails. We stub the external
    # executor and assert the raise.
    a = agent
    _stub_tool_executor(a, "Tests: 5 passed 5 total")
    with patch.object(a, "run_lint_gate", return_value="[eslint] boom"), patch.object(
        a, "_backup_generated_files"
    ):
        with pytest.raises(LintError):
            a.process(
                {
                    "existing_tests_passed": 0,
                    "existing_coverage_all_files": 0.0,
                    "result": {},
                }
            )


def test_lint_gate_none_when_clean(agent):
    with patch("subprocess.run", return_value=_mock_run(0, stdout="")):
        assert agent.run_lint_gate() is None


def test_lint_gate_skips_missing_binary(agent):
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        assert agent.run_lint_gate() is None


# --- §3.3 Strict-growth gate --------------------------------------------------
def test_strict_growth_raises_when_no_growth(agent):
    # jest passed but count unchanged -> TestRecoveryNeeded.
    a = agent
    _stub_tool_executor(a, "Tests: 5 passed 5 total")
    with patch.object(a, "run_lint_gate", return_value=None), patch.object(
        a, "_backup_generated_files"
    ), patch.object(a, "_enforce_no_omission"):
        with pytest.raises(TestRecoveryNeeded):
            a.process(
                {
                    "existing_tests_passed": 5,  # equal -> no growth
                    "existing_coverage_all_files": 0.0,
                    "result": {},
                }
            )


def test_strict_growth_passes_when_count_grew(agent):
    a = agent
    _stub_tool_executor(a, "Tests: 6 passed 6 total")
    with patch.object(a, "run_lint_gate", return_value=None), patch.object(
        a, "_backup_generated_files"
    ), patch.object(a, "_enforce_no_omission"):
        out = a.process(
            {
                "existing_tests_passed": 5,
                "existing_coverage_all_files": 0.0,
                "result": {},
            }
        )
        assert out["post_integration_tests_passed"] == 6


# --- §4.4 Omission guard ------------------------------------------------------
def test_omission_guard_restores_and_raises(agent):
    src_dir = agent.project_root
    os.makedirs(os.path.join(src_dir, "src", "__tests__"), exist_ok=True)
    backups = os.path.join(src_dir, "backups", "20260101_000000")
    os.makedirs(backups, exist_ok=True)
    gen_code = os.path.join(src_dir, "src", "main.ts")
    with open(gen_code, "w") as f:
        f.write("x" * 200)
    with open(os.path.join(backups, "main.ts.backup"), "w") as f:
        f.write("x" * 1000)

    with pytest.raises(OmissionDetected):
        agent._enforce_no_omission()

    with open(gen_code) as f:
        assert len(f.read()) == 1000


def test_omission_guard_passes_when_no_shrink(agent):
    src_dir = agent.project_root
    os.makedirs(os.path.join(src_dir, "src", "__tests__"), exist_ok=True)
    backups = os.path.join(src_dir, "backups", "20260101_000000")
    os.makedirs(backups, exist_ok=True)
    gen_code = os.path.join(src_dir, "src", "main.ts")
    with open(gen_code, "w") as f:
        f.write("x" * 1200)
    with open(os.path.join(backups, "main.ts.backup"), "w") as f:
        f.write("x" * 1000)
    agent._enforce_no_omission()
    with open(gen_code) as f:
        assert len(f.read()) == 1200


def test_max_self_correct_attempts_is_five():
    assert MAX_SELF_CORRECT_ATTEMPTS == 5
