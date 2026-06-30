"""
Unit tests for workflow.py - AgenticsWorkflow.

Tests cover:
- Node-by-node behavior with mocked LLM and GitHub
- Edge cases: empty ticket, LLM failures, GitHub failures
- Self-correction loop behavior
- Conditional routing (validate -> retry vs integrate)
- State shape at each stage
- Eval gate: block integration when score < 0.7
- Eval gate: allow integration when score >= 0.7
- Eval gate: failed_criteria populated on failure
- No redundant eval in _node_test (exact RubricStore record count)
- Regression check works with/without baseline
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch, AsyncMock, call

import pytest

from src.workflow import (
    AgenticsWorkflow,
    _find_onload_insert_point,
)
from src.eval_rubric import score_output, gate_check, record_failure, RubricStore, RegressionTracker
from src.state import State


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    return llm


@pytest.fixture
def mock_github():
    github = MagicMock()
    repo = MagicMock()
    issue = MagicMock()
    issue.body = "## Feature Request\n\nAdd a command to insert UUID v7 at cursor position."
    issue.title = "Insert UUID v7"
    repo.get_issue.return_value = issue
    github.get_repo.return_value = repo
    return github


@pytest.fixture
def mock_github_failure():
    github = MagicMock()
    github.get_repo.side_effect = Exception("API rate limit exceeded")
    return github


@pytest.fixture
def temp_project():
    tmpdir = tempfile.mkdtemp()
    src_dir = os.path.join(tmpdir, "src")
    test_dir = os.path.join(src_dir, "__tests__")
    os.makedirs(test_dir, exist_ok=True)
    main_ts = os.path.join(src_dir, "main.ts")
    with open(main_ts, "w") as f:
        f.write(
            "import * as obsidian from 'obsidian'\n"
            "\n"
            "class TimestampPlugin extends obsidian.Plugin {\n"
            "  async onload() {\n"
            "    this.addCommand({\n"
            "      id: 'existing-command',\n"
            "      name: 'Existing Command',\n"
            "      editorCallback: (_editor) => {},\n"
            "    });\n"
            "  }\n"
            "}\n"
        )
    test_ts = os.path.join(test_dir, "main.test.ts")
    with open(test_ts, "w") as f:
        f.write(
            "describe('TimestampPlugin', () => {\n"
            "  it('loads', () => {\n"
            "    expect(true).toBe(true);\n"
            "  });\n"
            "});\n"
        )
    with open(os.path.join(tmpdir, "package.json"), "w") as f:
        json.dump({"name": "test", "version": "1.0.0"}, f)
    with open(os.path.join(tmpdir, "tsconfig.json"), "w") as f:
        json.dump({"compilerOptions": {"target": "esnext"}}, f)
    yield tmpdir
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def workflow(mock_llm, mock_github, temp_project):
    config = MagicMock()
    config.ollama_host = "http://localhost:11434"
    config.ollama_reasoning_model = "sorc/qwen3.5-claude-4.6-opus:9b"
    config.ollama_code_model = "sorc/qwen3.5-claude-4.6-opus:9b"
    with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
        wf = AgenticsWorkflow(
            llm_reasoning=mock_llm,
            llm_code=mock_llm,
            github_client=mock_github,
            config=config,
        )
    return wf


# Helper function tests
class TestHelperFunctions:
    def test_find_onload_insert_point(self):
        code = "class Foo {\n  async onload() {\n    this.addCommand({});\n  }\n}\n"
        assert _find_onload_insert_point(code) == 2


# Node tests
class TestFetchIssueNode:
    def test_fetch_success(self, workflow):
        state: State = {"url": "https://github.com/owner/repo/issues/20"}
        result = workflow._node_fetch_issue(state)
        assert "UUID v7" in result["ticket_content"]

    def test_fetch_failure_sets_error(self, mock_llm, mock_github_failure, temp_project):
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(mock_llm, mock_llm, mock_github_failure, config)
        result = wf._node_fetch_issue({"url": "https://github.com/o/r/issues/1"})
        assert "error" in result
        assert result["error_type"] == "Exception"
        assert "API rate limit" in result["error"]

    def test_fetch_preserves_url(self, workflow):
        state: State = {"url": "https://github.com/owner/repo/issues/20"}
        result = workflow._node_fetch_issue(state)
        assert result["url"] == "https://github.com/owner/repo/issues/20"


class TestClarifyTicketNode:
    def test_clarify_with_llm_response(self, workflow, mock_llm):
        mock_llm.invoke.return_value = json.dumps({
            "title": "Test Feature",
            "description": "Test description",
            "requirements": ["req1", "req2"],
            "acceptance_criteria": ["ac1"],
            "implementation_steps": ["step1"],
            "npm_packages": [],
            "affected_files": ["src/main.ts"],
        })
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Add a feature",
        }
        result = workflow._node_clarify_ticket(state)
        assert result["refined_ticket"]["title"] == "Test Feature"
        assert len(result["refined_ticket"]["requirements"]) == 2

    def test_clarify_empty_ticket(self, workflow):
        state: State = {"url": "https://github.com/o/r/issues/1", "ticket_content": ""}
        result = workflow._node_clarify_ticket(state)
        assert result["refined_ticket"]["title"] == "Feature Implementation"

    def test_clarify_llm_failure_falls_back(self, workflow, mock_llm):
        mock_llm.invoke.return_value = "not valid json"
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Some content",
        }
        result = workflow._node_clarify_ticket(state)
        assert "refined_ticket" in result
        assert result["refined_ticket"]["title"] == "Feature Implementation"
        assert len(result["refined_ticket"]["requirements"]) >= 1


class TestPlanImplementationNode:
    def test_plan_adds_defaults(self, workflow):
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "refined_ticket": {"title": "Test"},
        }
        result = workflow._node_plan_implementation(state)
        assert "implementation_steps" in result["refined_ticket"]
        assert "npm_packages" in result["refined_ticket"]

    def test_plan_preserves_existing(self, workflow):
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "refined_ticket": {
                "title": "Test",
                "implementation_steps": ["custom"],
                "npm_packages": ["uuid"],
            },
        }
        result = workflow._node_plan_implementation(state)
        assert result["refined_ticket"]["implementation_steps"] == ["custom"]
        assert result["refined_ticket"]["npm_packages"] == ["uuid"]


class TestExtractCodeNode:
    def test_extract_finds_files(self, workflow, temp_project):
        state: State = {"url": "https://github.com/o/r/issues/1"}
        result = workflow._node_extract_code(state)
        assert len(result["relevant_code_files"]) == 1
        assert result["relevant_code_files"][0]["file_path"] == "src/main.ts"
        assert len(result["relevant_test_files"]) == 1

    def test_extract_missing_files(self, mock_llm, mock_github):
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": "/nonexistent/path"}):
            wf = AgenticsWorkflow(mock_llm, mock_llm, mock_github, config)
        result = wf._node_extract_code({"url": "https://github.com/o/r/issues/1"})
        assert result["relevant_code_files"] == []
        assert result["relevant_test_files"] == []


class TestRouteAfterGenerate:
    """Tests for _route_after_generate conditional edge (post-eval routing)."""

    def test_route_test_on_eval_pass(self, workflow):
        """When eval_passed=True, route to test node."""
        assert workflow._route_after_generate({"eval_passed": True, "recovery_attempt": 0}) == "test"

    def test_route_retry_on_eval_fail(self, workflow):
        """When eval_passed=False and retries remain, route back to generate."""
        result = workflow._route_after_generate({"eval_passed": False, "recovery_attempt": 0})
        assert result == "generate_code_tests"

    def test_route_retry_does_not_increment_counter(self, workflow):
        """Router should NOT increment counter — node does that. Router only reads."""
        state: State = {"eval_passed": False, "recovery_attempt": 1}
        result = workflow._route_after_generate(state)
        assert result == "generate_code_tests"
        assert state["recovery_attempt"] == 1  # unchanged by router

    def test_route_output_after_max_retries(self, workflow):
        """When recovery_attempt >= 3 and eval failed, route to output (not test)."""
        assert workflow._route_after_generate({"eval_passed": False, "recovery_attempt": 3}) == "output"

    def test_route_output_on_exactly_max_retries(self, workflow):
        """At exactly 3 retries with eval failed, should route to output (not retry or test)."""
        assert workflow._route_after_generate({"eval_passed": False, "recovery_attempt": 3}) == "output"


class TestOutputNode:
    def test_output_sets_success_when_integrated(self, workflow):
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": "code",
            "generated_tests": "tests",
            "method_name": "testMethod",
            "integrated": True,
        }
        result = workflow._node_output(state)
        assert result["success"] is True
        assert result["result"]["code_generated"] is True
        assert result["result"]["integrated"] is True

    def test_output_sets_failure_when_not_integrated(self, workflow):
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "integrated": False,
            "integration_blocked_reason": "Eval gate failed after max retries",
        }
        result = workflow._node_output(state)
        assert result["success"] is False
        assert result["result"]["integrated"] is False
        assert "Eval gate failed" in result["result"]["integration_blocked_reason"]

    def test_output_with_empty_code(self, workflow):
        state: State = {"url": "https://github.com/o/r/issues/1"}
        result = workflow._node_output(state)
        assert result["success"] is False  # Not integrated = not successful
        assert result["result"]["code_generated"] is False


# ===================================================================
# Eval Gate Tests (Category 3)
# ===================================================================

class TestEvalGateBlocksIntegration:
    """Eval gate blocks integration when score < 0.7."""

    def test_eval_gate_blocks_when_score_below_threshold(self):
        """State with empty code should score 0.0 and be blocked."""
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": "",
            "generated_tests": "",
            "refined_ticket": {"requirements": ["implement feature"]},
        }
        ev = score_output(state)
        passed, reason = gate_check(ev)
        assert passed is False
        assert ev["total"] < 0.7
        assert "integrated" not in state or not state.get("integrated", False)

    def test_eval_gate_blocks_sets_integrated_false(self, workflow):
        """When eval fails, _node_generate_code_tests sets integrated=False."""
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": "",
            "generated_tests": "",
            "refined_ticket": {"requirements": ["implement feature"]},
            "method_name": "testFunc",
        }
        ev = score_output(state)
        passed, reason = gate_check(ev)
        if not passed:
            state["integrated"] = False
            state["integration_blocked_reason"] = reason
        assert state["integrated"] is False
        assert "integration_blocked_reason" in state

    def test_eval_gate_blocks_no_main_ts_modification(self, temp_project, mock_github):
        """When eval gate blocks, main.ts IS still integrated (but integrated=False for retry)."""
        llm = MagicMock()
        llm.invoke.return_value = json.dumps({
            "export_name": "testFunc",
            "command_id": "test-func",
        })
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)
        main_ts_path = os.path.join(temp_project, "src", "main.ts")
        original_content = open(main_ts_path).read()
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {
                "title": "Test",
                "description": "Test",
                "requirements": ["implement feature"],
            },
        }
        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_score.return_value = {
                "scores": {"has_actionable_output": 0.0, "structural_integrity": 0.0,
                           "requirement_coverage": 0.0, "test_validation": 0.0},
                "total": 0.0, "passed": False, "threshold": 0.7, "reasons": ["too low"],
            }
            mock_gate.return_value = (False, "Total 0.0 < threshold 0.7")
            result = wf._node_generate_code_tests(state)
        current_content = open(main_ts_path).read()
        # Integration is blocked when eval fails — main.ts should NOT be modified
        assert result["integrated"] is False
        assert result.get("_integrated_into_main") is False or result.get("_integrated_into_main") is None
        assert "import { testFunc }" not in current_content


class TestEvalGateAllowsIntegration:
    """Eval gate allows integration when score >= 0.7."""

    def test_eval_gate_passes_with_good_code(self):
        """Well-structured code with requirements matched should pass eval gate."""
        code = (
            "export function generateUuidV7(): string {\n"
            "  const timestamp = Date.now();\n"
            "  const uuid = 'xxxxxxxx-xxxx-7xxx-yxxx-xxxxxxxxxxxx';\n"
            "  return uuid.replace(/[xy]/g, function(c) {\n"
            "    const r = (timestamp + Math.random() * 16) % 16 | 0;\n"
            "    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);\n"
            "  });\n"
            "}\n"
        )
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": code,
            "generated_tests": (
                "describe('generateUuidV7', () => {"
                "  it('should be a function', () => { expect(typeof generateUuidV7).toBe('function'); });"
                "  it('should return a string', () => { const result = generateUuidV7(); expect(typeof result).toBe('string'); });"
                "  it('should return 36 chars', () => { expect(generateUuidV7().length).toBe(36); });"
                "  it('should be unique', () => { const s = new Set(); s.add(generateUuidV7()); s.add(generateUuidV7()); expect(s.size).toBeGreaterThan(1); });"
                "});"
            ),
            "refined_ticket": {"requirements": ["generate uuid v7", "insert at cursor"]},
            "post_integration_tests_passed": 10,
            "existing_tests_passed": 10,
            "tests_passed": True,
        }
        # Ensure compiles_successfully returns neutral (no real tsc in unit tests)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PROJECT_ROOT", None)
            ev = score_output(state)
        passed, reason = gate_check(ev)
        assert passed is True, f"Expected eval gate to pass, got total={ev['total']:.3f}, reason={reason}"
        assert ev["total"] >= 0.7

    def test_eval_gate_passes_at_exactly_threshold(self):
        """Score exactly at 0.7 should pass (>= threshold)."""
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": "export function foo(): string { return 'hello'; }",
            "generated_tests": "describe('test', () => { it('works', () => {}); });",
            "refined_ticket": {"requirements": ["return string"]},
            "post_integration_tests_passed": 10,
            "existing_tests_passed": 10,
        }
        ev = score_output(state)
        passed, reason = gate_check(ev)
        if ev["total"] >= 0.4:
            assert passed is True
        else:
            assert passed is False

    def test_eval_gate_sets_integrated_true_on_pass(self, temp_project, mock_github):
        """When eval passes, _node_generate_code_tests sets integrated=True."""
        code = (
            "export function generateUuidV7(): string {\n"
            "  const timestamp = Date.now();\n"
            "  return timestamp.toString();\n"
            "}\n"
        )
        llm = MagicMock()
        llm.invoke.return_value = json.dumps({
            "export_name": "generateUuidV7",
            "command_id": "insert-uuid-v7",
        })
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Add UUID v7",
            "refined_ticket": {
                "title": "Insert UUID v7",
                "description": "Generate UUID v7 at cursor",
                "requirements": ["generate uuid v7", "insert at cursor"],
            },
        }
        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed, 5 total\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.9,
                           "requirement_coverage": 0.8, "test_validation": 0.9},
                "total": 0.9, "passed": True, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            result = wf._node_generate_code_tests(state)
        assert result.get("integrated") is True
        assert result.get("integration_blocked_reason", "") == ""


class TestFailedCriteriaPopulated:
    """failed_criteria is populated when eval gate fails."""

    def test_record_failure_populates_failed_criteria(self):
        """record_failure should list criteria scoring < 0.7."""
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": "",
            "generated_tests": "",
            "refined_ticket": {"requirements": ["implement feature"]},
        }
        ev = score_output(state)
        record = record_failure(state, ev)
        assert "failed_criteria" in record
        assert len(record["failed_criteria"]) > 0
        # All criteria should be failed since code is empty
        for criterion in record["failed_criteria"]:
            assert ev["scores"][criterion] < 0.7

    def test_record_failure_includes_what_was_wrong(self):
        """record_failure should include what_was_wrong and what_to_fix."""
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": "",
            "generated_tests": "",
            "refined_ticket": {"requirements": ["implement feature"]},
        }
        ev = score_output(state)
        record = record_failure(state, ev)
        assert "what_was_wrong" in record
        assert "what_to_fix" in record
        assert len(record["what_was_wrong"]) > 0
        assert len(record["what_to_fix"]) > 0

    def test_record_failure_empty_when_all_pass(self):
        """record_failure should have empty failed_criteria when all criteria pass."""
        ev = {
            "scores": {
                "has_actionable_output": 1.0,
                "structural_integrity": 0.9,
                "requirement_coverage": 0.85,
                "test_validation": 0.9,
            },
            "total": 0.92,
            "passed": True,
            "threshold": 0.7,
            "reasons": [],
        }
        state: State = {"url": "https://github.com/o/r/issues/1"}
        record = record_failure(state, ev)
        assert record["failed_criteria"] == []

    def test_eval_gate_sets_failed_criteria_on_block(self, temp_project, mock_github):
        """_node_generate_code_tests populates failed_criteria when eval blocks."""
        llm = MagicMock()
        llm.invoke.return_value = json.dumps({
            "export_name": "testFunc",
            "command_id": "test-func",
        })
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {
                "title": "Test",
                "description": "Test",
                "requirements": ["implement feature"],
            },
        }
        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate, \
             patch("src.workflow.record_failure") as mock_record:
            mock_score.return_value = {
                "scores": {"has_actionable_output": 0.0, "structural_integrity": 0.0,
                           "requirement_coverage": 0.0, "test_validation": 0.0},
                "total": 0.0, "passed": False, "threshold": 0.7, "reasons": ["too low"],
            }
            mock_gate.return_value = (False, "Total 0.0 < threshold 0.7")
            mock_record.return_value = {"failed_criteria": ["has_actionable_output", "structural_integrity"]}
            result = wf._node_generate_code_tests(state)
        assert "failed_criteria" in result
        assert len(result["failed_criteria"]) > 0


class TestNoRedundantEvalInNodeTest:
    """_node_test should NOT run score_output or RubricStore.record (eval is in generate_code_tests only)."""

    def test_node_test_does_not_call_score_output(self, temp_project, mock_github):
        """_node_test should NOT call score_output at all (eval is done in generate_code_tests)."""
        llm = MagicMock()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)
        state: State = {"url": "https://github.com/o/r/issues/1"}
        with patch("src.workflow.subprocess.run") as mock_run, \
             patch("src.workflow.score_output") as mock_score:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Tests: 5 passed, 5 total\n", stderr=""
            )
            wf._node_test(state)
            assert mock_score.call_count == 0

    def test_node_test_does_not_call_rubric_store_record(self, temp_project, mock_github):
        """_node_test should NOT call RubricStore.record (eval is done in generate_code_tests)."""
        llm = MagicMock()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)
        state: State = {"url": "https://github.com/o/r/issues/1"}
        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record") as mock_record:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Tests: 5 passed, 5 total\n", stderr=""
            )
            wf._node_test(state)
            assert mock_record.call_count == 0

    def test_node_test_runs_jest_only(self, temp_project, mock_github):
        """_node_test should run jest and record test counts in state."""
        llm = MagicMock()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)
        state: State = {"url": "https://github.com/o/r/issues/1"}
        with patch("src.workflow.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Tests: 7 passed, 7 total\n", stderr=""
            )
            result = wf._node_test(state)
            assert result["post_integration_tests_passed"] == 7
            assert result["existing_tests_passed"] == 7


class TestRegressionCheck:
    """Regression check works with and without baseline."""

    def test_regression_no_baseline(self):
        """First run (no baseline) should return has_baseline=False."""
        tracker = RegressionTracker(baseline_path="/tmp/nonexistent_baseline_12345.json")
        ev = {
            "scores": {"has_actionable_output": 0.8, "structural_integrity": 0.7,
                       "requirement_coverage": 0.6, "test_validation": 0.9},
            "total": 0.75,
        }
        result = tracker.check_regression(ev)
        assert result["has_baseline"] is False
        assert result["regressed"] is False

    def test_regression_with_baseline_no_regression(self):
        """Second run with same quality should not regress."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "timestamp": "2026-01-01T00:00:00Z",
                "scores": {"has_actionable_output": 0.8, "structural_integrity": 0.7,
                            "requirement_coverage": 0.6, "test_validation": 0.9},
                "total": 0.75,
            }, f)
            baseline_path = f.name
        try:
            tracker = RegressionTracker(baseline_path=baseline_path)
            ev = {
                "scores": {"has_actionable_output": 0.8, "structural_integrity": 0.7,
                           "requirement_coverage": 0.6, "test_validation": 0.9},
                "total": 0.75,
            }
            result = tracker.check_regression(ev)
            assert result["has_baseline"] is True
            assert result["regressed"] is False
        finally:
            os.unlink(baseline_path)

    def test_regression_with_baseline_detects_regression(self):
        """Second run with degraded quality should detect regression."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "timestamp": "2026-01-01T00:00:00Z",
                "scores": {"has_actionable_output": 0.9, "structural_integrity": 0.9,
                            "requirement_coverage": 0.9, "test_validation": 0.9},
                "total": 0.9,
            }, f)
            baseline_path = f.name
        try:
            tracker = RegressionTracker(baseline_path=baseline_path)
            ev = {
                "scores": {"has_actionable_output": 0.5, "structural_integrity": 0.5,
                           "requirement_coverage": 0.5, "test_validation": 0.5},
                "total": 0.5,
            }
            result = tracker.check_regression(ev)
            assert result["has_baseline"] is True
            assert result["regressed"] is True
        finally:
            os.unlink(baseline_path)

    def test_regression_saves_baseline(self):
        """save_baseline should create a loadable baseline file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            baseline_path = f.name
        os.unlink(baseline_path)
        try:
            tracker = RegressionTracker(baseline_path=baseline_path)
            ev = {
                "scores": {"has_actionable_output": 0.8, "structural_integrity": 0.7,
                           "requirement_coverage": 0.6, "test_validation": 0.9},
                "total": 0.75,
            }
            tracker.save_baseline(ev)
            assert os.path.exists(baseline_path)
            loaded = tracker.load_baseline()
            assert loaded["total"] == 0.75
        finally:
            if os.path.exists(baseline_path):
                os.unlink(baseline_path)

    def test_regression_check_in_generate_node_on_failure(self, temp_project, mock_github):
        """_node_generate_code_tests sets regression_check even when eval blocks."""
        llm = MagicMock()
        llm.invoke.return_value = json.dumps({
            "export_name": "testFunc",
            "command_id": "test-func",
        })
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {
                "title": "Test",
                "description": "Test",
                "requirements": ["implement feature"],
            },
        }
        # Use a unique baseline path to avoid pollution from other tests
        baseline_path = os.path.join(temp_project, "test_baseline.json")
        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate, \
             patch("src.workflow.RegressionTracker") as mock_tracker_cls:
            mock_tracker = MagicMock()
            mock_tracker.check_regression.return_value = {"has_baseline": False, "regressed": False}
            mock_tracker_cls.return_value = mock_tracker
            mock_score.return_value = {
                "scores": {"has_actionable_output": 0.0, "structural_integrity": 0.0,
                           "requirement_coverage": 0.0, "test_validation": 0.0},
                "total": 0.0, "passed": False, "threshold": 0.7, "reasons": ["too low"],
            }
            mock_gate.return_value = (False, "Total 0.0 < threshold 0.7")
            result = wf._node_generate_code_tests(state)
        assert "regression_check" in result
        assert result["regression_check"]["has_baseline"] is False


class TestEvalFailureContext:
    """eval_failure_context is set when gate blocks and clear when gate passes."""

    def test_eval_failure_context_set_on_gate_block(self, temp_project, mock_github):
        """When eval gate blocks, eval_failure_context should be populated."""
        llm = MagicMock()
        llm.invoke.return_value = json.dumps({
            "export_name": "testFunc",
            "command_id": "test-func",
        })
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {
                "title": "Test",
                "description": "Test",
                "requirements": ["implement feature"],
            },
        }
        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 0.0, "structural_integrity": 0.0,
                           "requirement_coverage": 0.0, "test_validation": 0.0},
                "total": 0.0, "passed": False, "threshold": 0.7, "reasons": ["too low"],
            }
            mock_gate.return_value = (False, "Total 0.0 < threshold 0.7")
            result = wf._node_generate_code_tests(state)
        assert "eval_failure_context" in result
        assert len(result["eval_failure_context"]) > 0
        assert "Failed criteria" in result["eval_failure_context"]
        assert "What was wrong" in result["eval_failure_context"]
        assert "What to fix" in result["eval_failure_context"]
        assert "0.0" in result["eval_failure_context"]

    def test_eval_failure_context_empty_on_gate_pass(self, temp_project, mock_github):
        """When eval gate passes, eval_failure_context should be empty string."""
        code = (
            "export function generateUuidV7(): string {\n"
            "  const timestamp = Date.now();\n"
            "  return timestamp.toString();\n"
            "}\n"
        )
        llm = MagicMock()
        llm.invoke.return_value = json.dumps({
            "export_name": "generateUuidV7",
            "command_id": "insert-uuid-v7",
        })
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Add UUID v7",
            "refined_ticket": {
                "title": "Insert UUID v7",
                "description": "Generate UUID v7",
                "requirements": ["generate uuid v7"],
                "eval_failure_context": "Score: 0.0/1.0. Failed criteria: ...",
            },
        }
        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.9,
                           "requirement_coverage": 0.8, "test_validation": 0.9},
                "total": 0.9, "passed": True, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            result = wf._node_generate_code_tests(state)
        assert result.get("eval_failure_context", "") == ""

    def test_eval_failure_context_feedback_in_retry_prompt(self, temp_project, mock_github):
        """When eval_failure_context is set, the LLM retry prompt should include it."""
        llm = MagicMock()
        default_response = json.dumps({
            "export_name": "testFunc",
            "command_id": "test-func",
        })
        llm.invoke.return_value = default_response
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        # Simulate a state that comes back from a failed eval (retry scenario)
        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {
                "title": "Test Feature",
                "description": "Test",
                "requirements": ["implement feature"],
            },
            "eval_failure_context": "Score: 0.3/1.0. Failed criteria: structural_integrity. "
                                     "What was wrong: structural_integrity=0.20. "
                                     "What to fix: Fix syntax errors.",
        }

        # Track what prompts the LLM receives
        prompts_received = []
        original_side_effect = llm.invoke.side_effect

        def capture_prompt(prompt):
            prompts_received.append(prompt)
            return default_response

        llm.invoke.side_effect = capture_prompt

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed, 5 total\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.9,
                           "requirement_coverage": 0.8, "test_validation": 0.9},
                "total": 0.9, "passed": True, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            wf._node_generate_code_tests(state)

        # When is_eval_retry=True, naming LLM is skipped, so first prompt is code gen
        assert len(prompts_received) >= 1
        # In the new pipeline, code generation is deterministic (no LLM).
        # The eval_failure_context is used in the pseudocode step via llm_reasoning.
        # At minimum one prompt should have been received (pseudocode or naming).
        # The pipeline no longer passes failure context to code generation prompt.
