"""
Integration tests for the eval gate behavior in _node_generate_code_tests.

Covers:
1) Score >= 0.7 -> integration proceeds (main.ts written).
2) Score < 0.7 -> integration blocked (main.ts NOT written).
3) Scores logged to RubricStore on every run.
4) Regression check result in state after integration.

All tests use mocked LLM (no Ollama needed).
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch, call

import pytest

from src.workflow import AgenticsWorkflow
from src.state import State
from src.eval_rubric import RubricStore, RegressionTracker, score_output, gate_check


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


# Helper: standard LLM side_effect for passing tests
def _passing_llm_side_effect(export_name="generateUuidV7", command_id="insert-uuid-v7",
                              title="Insert UUID v7"):
    code = (f"export function {export_name}(): string {{\n"
            f"  const timestamp = Date.now();\n"
            f"  return timestamp.toString();\n"
            f"}}\n")
    slug = command_id
    tests = (f"import {{ {export_name} }} from '../../generated/{slug}';\n"
             f"describe('{export_name}', () => {{\n"
             f"  it('should be a function', () => {{ expect(typeof {export_name}).toBe('function'); }});\n"
             f"  it('should return a string', () => {{ expect(typeof {export_name}()).toBe('string'); }});\n"
             f"}});\n")
    # Return enough values for all LLM calls (naming + code + test + potential retries)
    # Each call consumes one value from the list
    return [
        json.dumps({"export_name": export_name, "command_id": command_id}),
        code,
        tests,
        # Retry values (if needed)
        code,
        tests,
        code,
        tests,
    ]


# ---------------------------------------------------------------------------
# 1) Score >= 0.7 -> integration proceeds (main.ts written)
# ---------------------------------------------------------------------------

class TestEvalPassIntegration:
    """Score >= 0.7 triggers integration: main.ts is modified with import + addCommand."""

    def test_score_0_7_exact_threshold_integrates(self, temp_project, mock_github):
        """Score exactly at 0.7 threshold -> integration proceeds."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect()
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

        main_ts_path = os.path.join(temp_project, "src", "main.ts")
        original_main = open(main_ts_path).read()

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record") as mock_record, \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed, 5 total\n", stderr="")
            mock_score.return_value = {
                "scores": {
                    "has_actionable_output": 1.0,
                    "structural_integrity": 0.7,
                    "requirement_coverage": 0.7,
                    "test_validation": 0.7,
                },
                "total": 0.7,
                "passed": True,
                "threshold": 0.7,
                "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            result = wf._node_generate_code_tests(state)

        assert result["integrated"] is True
        assert result["eval_passed"] is True
        assert result["integration_blocked_reason"] == ""
        current_main = open(main_ts_path).read()
        assert current_main != original_main
        assert "generateUuidV7" in current_main

        # Verify main.test.ts was also updated with integration tests
        main_test_path = os.path.join(temp_project, "src", "__tests__", "main.test.ts")
        current_test = open(main_test_path).read()
        assert "Integration: insert-uuid-v7 command" in current_test
        assert "should register the insert-uuid-v7 command" in current_test

    def test_score_above_0_7_integrates(self, temp_project, mock_github):
        """Score well above 0.7 -> integration proceeds."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Add UUID v7",
            "refined_ticket": {
                "title": "Insert UUID v7",
                "description": "Generate UUID v7 at cursor",
                "requirements": ["generate uuid v7"],
            },
        }

        main_ts_path = os.path.join(temp_project, "src", "main.ts")
        original_main = open(main_ts_path).read()

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed, 5 total\n", stderr="")
            mock_score.return_value = {
                "scores": {
                    "has_actionable_output": 1.0,
                    "structural_integrity": 0.95,
                    "requirement_coverage": 0.85,
                    "test_validation": 0.9,
                },
                "total": 0.93,
                "passed": True,
                "threshold": 0.7,
                "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            result = wf._node_generate_code_tests(state)

        assert result["integrated"] is True
        current_main = open(main_ts_path).read()
        assert current_main != original_main
        assert "generateUuidV7" in current_main
        assert "insert-uuid-v7" in current_main

    def test_main_ts_contains_import_line_on_integration(self, temp_project, mock_github):
        """After integration, main.ts contains the import line for the generated module."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect(
            export_name="myFeature", command_id="my-feature", title="My Feature")
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Add feature",
            "refined_ticket": {
                "title": "My Feature",
                "requirements": ["implement feature"],
            },
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 3 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.9,
                           "requirement_coverage": 0.8, "test_validation": 0.9},
                "total": 0.9, "passed": True, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            wf._node_generate_code_tests(state)

        current_main = open(os.path.join(temp_project, "src", "main.ts")).read()
        assert "import { myFeature } from './generated/my-feature'" in current_main

    def test_main_ts_contains_addcommand_on_integration(self, temp_project, mock_github):
        """After integration, main.ts contains the addCommand block for the new command."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect(
            export_name="myFeature", command_id="my-feature", title="My Feature")
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Add feature",
            "refined_ticket": {
                "title": "My Feature",
                "requirements": ["implement feature"],
            },
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 3 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.9,
                           "requirement_coverage": 0.8, "test_validation": 0.9},
                "total": 0.9, "passed": True, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            wf._node_generate_code_tests(state)

        current_main = open(os.path.join(temp_project, "src", "main.ts")).read()
        assert "this.addCommand" in current_main
        assert "'my-feature'" in current_main
        assert "myFeature()" in current_main


# ---------------------------------------------------------------------------
# 2) Score < 0.7 -> integration blocked (main.ts NOT written)
# ---------------------------------------------------------------------------

class TestEvalFailBlocksIntegration:
    """Score < 0.7 blocks integration: main.ts is NOT modified."""

    def test_score_0_69_blocks_integration(self, temp_project, mock_github):
        """Score just below 0.7 threshold -> integration blocked."""
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
                "requirements": ["implement feature"],
            },
        }

        main_ts_path = os.path.join(temp_project, "src", "main.ts")
        original_main = open(main_ts_path).read()

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record") as mock_record, \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed, 5 total\n", stderr="")
            mock_score.return_value = {
                "scores": {
                    "has_actionable_output": 1.0,
                    "structural_integrity": 0.5,
                    "requirement_coverage": 0.5,
                    "test_validation": 0.5,
                },
                "total": 0.69,
                "passed": False,
                "threshold": 0.7,
                "reasons": ["Low score"],
            }
            mock_gate.return_value = (False, "Total 0.69 < threshold 0.7")
            result = wf._node_generate_code_tests(state)

        assert result["integrated"] is False
        assert result["eval_passed"] is False
        current_main = open(main_ts_path).read()
        assert current_main == original_main

    def test_score_zero_blocks_integration(self, temp_project, mock_github):
        """Score of 0.0 -> integration completely blocked."""
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
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        main_ts_path = os.path.join(temp_project, "src", "main.ts")
        original_main = open(main_ts_path).read()

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 0.0, "structural_integrity": 0.0,
                           "requirement_coverage": 0.0, "test_validation": 0.0},
                "total": 0.0, "passed": False, "threshold": 0.7, "reasons": ["All zero"],
            }
            mock_gate.return_value = (False, "Total 0.0 < threshold 0.7")
            result = wf._node_generate_code_tests(state)

        assert result["integrated"] is False
        current_main = open(main_ts_path).read()
        assert current_main == original_main

    def test_integration_blocked_reason_populated_on_failure(self, temp_project, mock_github):
        """integration_blocked_reason is set when eval gate fails."""
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
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 0.5, "structural_integrity": 0.3,
                           "requirement_coverage": 0.4, "test_validation": 0.5},
                "total": 0.43,
                "passed": False,
                "threshold": 0.7,
                "reasons": ["structural_integrity too low"],
            }
            mock_gate.return_value = (False, "Total 0.43 < threshold 0.7")
            result = wf._node_generate_code_tests(state)

        assert result["integration_blocked_reason"] != ""
        assert "0.43" in result["integration_blocked_reason"] or "0.7" in result["integration_blocked_reason"]

    def test_failed_criteria_populated_on_eval_failure(self, temp_project, mock_github):
        """failed_criteria lists the criteria that scored below threshold."""
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
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.2,
                           "requirement_coverage": 0.3, "test_validation": 0.8},
                "total": 0.55,
                "passed": False,
                "threshold": 0.7,
                "reasons": ["structural_integrity too low"],
            }
            mock_gate.return_value = (False, "fail")
            result = wf._node_generate_code_tests(state)

        assert "failed_criteria" in result
        assert len(result["failed_criteria"]) > 0
        # structural_integrity and requirement_coverage should be in failed criteria
        assert "structural_integrity" in result["failed_criteria"]
        assert "requirement_coverage" in result["failed_criteria"]

    def test_no_addcommand_in_main_ts_when_blocked(self, temp_project, mock_github):
        """When blocked, main.ts does NOT contain a new addCommand for the generated function."""
        llm = MagicMock()
        llm.invoke.return_value = json.dumps({
            "export_name": "blockedFunc",
            "command_id": "blocked-func",
        })
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 0.0, "structural_integrity": 0.0,
                           "requirement_coverage": 0.0, "test_validation": 0.0},
                "total": 0.0, "passed": False, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (False, "fail")
            wf._node_generate_code_tests(state)

        current_main = open(os.path.join(temp_project, "src", "main.ts")).read()
        assert "blockedFunc" not in current_main
        assert "blocked-func" not in current_main


# ---------------------------------------------------------------------------
# 3) Scores logged to RubricStore on every run
# ---------------------------------------------------------------------------

class TestRubricStoreLogging:
    """RubricStore.record is called exactly once per _node_generate_code_tests call."""

    def test_rubric_store_called_on_eval_pass(self, temp_project, mock_github):
        """RubricStore.record is called when eval passes."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record") as mock_record, \
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
            wf._node_generate_code_tests(state)

        assert mock_record.call_count == 1

    def test_rubric_store_called_on_eval_failure(self, temp_project, mock_github):
        """RubricStore.record is called even when eval fails."""
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
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record") as mock_record, \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 0.0, "structural_integrity": 0.0,
                           "requirement_coverage": 0.0, "test_validation": 0.0},
                "total": 0.0, "passed": False, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (False, "fail")
            wf._node_generate_code_tests(state)

        assert mock_record.call_count == 1

    def test_rubric_store_called_exactly_once_not_twice(self, temp_project, mock_github):
        """RubricStore.record is called exactly once, not multiple times."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record") as mock_record, \
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
            wf._node_generate_code_tests(state)

        # Must be exactly 1, not 0 and not > 1
        assert mock_record.call_count == 1

    def test_rubric_store_receives_full_score_result(self, temp_project, mock_github):
        """RubricStore.record receives the full score result dict with scores, total, passed, threshold."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        expected_result = {
            "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.8,
                       "requirement_coverage": 0.75, "test_validation": 0.85},
            "total": 0.85,
            "passed": True,
            "threshold": 0.7,
            "reasons": [],
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record") as mock_record, \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output", return_value=expected_result), \
             patch("src.workflow.gate_check", return_value=(True, "ok")):
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            wf._node_generate_code_tests(state)

        assert mock_record.call_count == 1
        recorded = mock_record.call_args[0][0]
        assert "scores" in recorded
        assert "total" in recorded
        assert "passed" in recorded
        assert "threshold" in recorded
        assert recorded["total"] == 0.85
        assert recorded["passed"] is True

    def test_rubric_store_called_on_boundary_score(self, temp_project, mock_github):
        """RubricStore.record is called even at the exact boundary score of 0.7."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record") as mock_record, \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate:
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.7,
                           "requirement_coverage": 0.7, "test_validation": 0.7},
                "total": 0.7, "passed": True, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            wf._node_generate_code_tests(state)

        assert mock_record.call_count == 1


# ---------------------------------------------------------------------------
# 4) Regression check result in state after integration
# ---------------------------------------------------------------------------

class TestRegressionCheckInState:
    """Regression check is populated in state after _node_generate_code_tests."""

    def test_regression_check_present_after_pass(self, temp_project, mock_github):
        """regression_check is in state after eval passes and integration proceeds."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate, \
             patch("src.workflow.RegressionTracker") as mock_rt_cls:
            mock_rt = MagicMock()
            mock_rt.check_regression.return_value = {
                "has_baseline": False, "regressed": False, "deltas": {},
            }
            mock_rt_cls.return_value = mock_rt
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.9,
                           "requirement_coverage": 0.8, "test_validation": 0.9},
                "total": 0.9, "passed": True, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            result = wf._node_generate_code_tests(state)

        assert "regression_check" in result
        assert result["regression_check"]["has_baseline"] is False
        assert result["regression_check"]["regressed"] is False

    def test_regression_check_present_after_failure(self, temp_project, mock_github):
        """regression_check is in state even when eval fails and integration is blocked."""
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
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate, \
             patch("src.workflow.RegressionTracker") as mock_rt_cls:
            mock_rt = MagicMock()
            mock_rt.check_regression.return_value = {
                "has_baseline": True, "regressed": True,
                "deltas": {"structural_integrity": -0.3, "requirement_coverage": -0.2},
                "total_delta": -0.25, "baseline_total": 0.9, "current_total": 0.65,
            }
            mock_rt_cls.return_value = mock_rt
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 0.5, "structural_integrity": 0.3,
                           "requirement_coverage": 0.4, "test_validation": 0.5},
                "total": 0.43, "passed": False, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (False, "fail")
            result = wf._node_generate_code_tests(state)

        assert "regression_check" in result
        assert result["regression_check"]["has_baseline"] is True
        assert result["regression_check"]["regressed"] is True
        assert result["regression_check"]["total_delta"] == -0.25

    def test_regression_check_with_baseline_comparison(self, temp_project, mock_github):
        """Regression check compares against baseline when one exists."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate, \
             patch("src.workflow.RegressionTracker") as mock_rt_cls:
            mock_rt = MagicMock()
            mock_rt.check_regression.return_value = {
                "has_baseline": True,
                "regressed": False,
                "deltas": {"has_actionable_output": 0.0, "structural_integrity": 0.05,
                           "requirement_coverage": -0.02, "test_validation": 0.01},
                "total_delta": 0.01,
                "baseline_total": 0.88,
                "current_total": 0.89,
            }
            mock_rt_cls.return_value = mock_rt
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.9,
                           "requirement_coverage": 0.85, "test_validation": 0.9},
                "total": 0.89, "passed": True, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            result = wf._node_generate_code_tests(state)

        assert result["regression_check"]["has_baseline"] is True
        assert result["regression_check"]["regressed"] is False
        assert result["regression_check"]["current_total"] == 0.89
        assert result["regression_check"]["baseline_total"] == 0.88

    def test_baseline_saved_after_successful_integration(self, temp_project, mock_github):
        """Baseline is saved after eval passes and integration completes."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Test",
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate, \
             patch("src.workflow.RegressionTracker") as mock_rt_cls:
            mock_rt = MagicMock()
            mock_rt.check_regression.return_value = {"has_baseline": False, "regressed": False}
            mock_rt_cls.return_value = mock_rt
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.9,
                           "requirement_coverage": 0.8, "test_validation": 0.9},
                "total": 0.9, "passed": True, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (True, "ok")
            wf._node_generate_code_tests(state)

            # save_baseline should be called after integration
            mock_rt.save_baseline.assert_called_once()

    def test_baseline_not_saved_when_eval_fails(self, temp_project, mock_github):
        """Baseline is NOT saved when eval fails (integration blocked)."""
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
            "refined_ticket": {"title": "Test", "requirements": ["req"]},
        }

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow.score_output") as mock_score, \
             patch("src.workflow.gate_check") as mock_gate, \
             patch("src.workflow.RegressionTracker") as mock_rt_cls:
            mock_rt = MagicMock()
            mock_rt.check_regression.return_value = {"has_baseline": False, "regressed": False}
            mock_rt_cls.return_value = mock_rt
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            mock_score.return_value = {
                "scores": {"has_actionable_output": 0.0, "structural_integrity": 0.0,
                           "requirement_coverage": 0.0, "test_validation": 0.0},
                "total": 0.0, "passed": False, "threshold": 0.7, "reasons": [],
            }
            mock_gate.return_value = (False, "fail")
            wf._node_generate_code_tests(state)

            # save_baseline should NOT be called when eval fails
            mock_rt.save_baseline.assert_not_called()


# ---------------------------------------------------------------------------
# Combined: eval gate end-to-end with real score_output and gate_check
# ---------------------------------------------------------------------------

class TestEvalGateEndToEnd:
    """Tests using real score_output and gate_check (no mocking of eval logic)."""

    def test_real_score_above_threshold_integrates(self, temp_project, mock_github):
        """Using real score_output: high-quality state passes gate and integrates."""
        llm = MagicMock()
        llm.invoke.side_effect = _passing_llm_side_effect()
        config = MagicMock()
        with patch.dict(os.environ, {"PROJECT_ROOT": temp_project}):
            wf = AgenticsWorkflow(llm, llm, mock_github, config)

        state: State = {
            "url": "https://github.com/o/r/issues/1",
            "ticket_content": "Add UUID v7 at cursor position",
            "refined_ticket": {
                "title": "Insert UUID v7",
                "description": "Generate UUID v7 at cursor",
                "requirements": ["generate uuid v7", "insert at cursor", "timestamp-based"],
            },
        }

        main_ts_path = os.path.join(temp_project, "src", "main.ts")
        original_main = open(main_ts_path).read()

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"), \
             patch("src.workflow._post_process_generated_code", side_effect=lambda x: x):
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed, 5 total\n", stderr="")
            result = wf._node_generate_code_tests(state)

        # With real scoring, this should pass (good code + tests + requirements match)
        assert result["integrated"] is True
        assert result["eval_passed"] is True
        current_main = open(main_ts_path).read()
        assert current_main != original_main

    def test_real_score_below_threshold_blocks(self, temp_project, mock_github):
        """Using real score_output: low-quality state fails gate and blocks integration."""
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
            "ticket_content": "Add UUID v7 at cursor position",
            "refined_ticket": {
                "title": "Insert UUID v7",
                "description": "Generate UUID v7 at cursor",
                "requirements": ["generate uuid v7", "insert at cursor", "timestamp-based"],
            },
        }

        main_ts_path = os.path.join(temp_project, "src", "main.ts")
        original_main = open(main_ts_path).read()

        with patch("src.workflow.subprocess.run") as mock_run, \
             patch.object(RubricStore, "record"):
            mock_run.return_value = MagicMock(returncode=0, stdout="Tests: 5 passed\n", stderr="")
            result = wf._node_generate_code_tests(state)

        # Empty code -> has_actionable_output=0, requirement_coverage=0 -> should fail
        assert result["integrated"] is False
        assert result["eval_passed"] is False
        current_main = open(main_ts_path).read()
        assert current_main == original_main
