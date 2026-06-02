"""
Unit tests for eval gate behavior in workflow.

Tests cover:
- gate_check() returns (True, msg) when score >= threshold
- gate_check() returns (False, msg) when score < threshold
- record_failure() extracts failed_criteria from eval scores
- RegressionTracker saves baseline on pass, check_regression detects changes
- RubricStore.record() stores exactly one entry per call
- Score output ordering: score_output called before gate_check
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.eval_rubric import score_output, gate_check, record_failure, RubricStore, RegressionTracker


class TestEvalGate:
    """gate_check() returns correct (bool, reason) based on score vs threshold."""

    def test_gate_allows_on_high_score(self):
        result = {"total": 0.9, "passed": True, "threshold": 0.7, "reasons": []}
        passed, reason = gate_check(result)
        assert passed is True
        assert "ok" in reason.lower()

    def test_gate_blocks_on_low_score(self):
        result = {"total": 0.3, "passed": False, "threshold": 0.7, "reasons": ["low quality"]}
        passed, reason = gate_check(result)
        assert passed is False
        assert reason == "low quality"

    def test_gate_blocks_with_auto_reason_when_no_reasons(self):
        """When reasons list is empty, gate_check synthesizes a reason from total/threshold."""
        result = {"total": 0.3, "passed": False, "threshold": 0.7, "reasons": []}
        passed, reason = gate_check(result)
        assert passed is False
        assert "0.3" in reason and "0.7" in reason

    def test_gate_at_exact_threshold(self):
        result = {"total": 0.7, "passed": True, "threshold": 0.7, "reasons": []}
        passed, reason = gate_check(result)
        assert passed is True

    def test_gate_just_below_threshold(self):
        result = {"total": 0.69, "passed": False, "threshold": 0.7, "reasons": ["marginal"]}
        passed, reason = gate_check(result)
        assert passed is False


class TestEvalGateRecordsFailureCriteria:
    """record_failure() extracts failed_criteria from eval scores."""

    def test_records_failed_criteria_on_low_score(self):
        state = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": "export function test() { return ''; }",
        }
        ev = {
            "scores": {"has_actionable_output": 0.2, "structural_integrity": 0.3,
                       "requirement_coverage": 0.1, "test_validation": 0.0},
            "total": 0.15, "passed": False, "threshold": 0.7,
            "reasons": ["has_actionable_output: 0.2 < 0.5"],
        }
        result = record_failure(state, ev)
        assert "failed_criteria" in result
        assert len(result["failed_criteria"]) > 0

    def test_records_what_to_fix(self):
        state = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": "export function test() { return ''; }",
        }
        ev = {
            "scores": {"has_actionable_output": 0.2, "structural_integrity": 0.8,
                       "requirement_coverage": 0.1, "test_validation": 0.9},
            "total": 0.5, "passed": False, "threshold": 0.7,
            "reasons": ["has_actionable_output: 0.2 < 0.5"],
        }
        result = record_failure(state, ev)
        assert "what_to_fix" in result
        assert len(result["what_to_fix"]) > 0

    def test_all_scores_high_returns_dict(self):
        state = {"url": "https://github.com/o/r/issues/1"}
        ev = {
            "scores": {"has_actionable_output": 0.9, "structural_integrity": 0.9,
                       "requirement_coverage": 0.8, "test_validation": 0.9},
            "total": 0.875, "passed": True, "threshold": 0.7, "reasons": [],
        }
        result = record_failure(state, ev)
        assert isinstance(result, dict)


class TestScoreOutput:
    """score_output() produces a valid eval dict."""

    def test_score_output_returns_required_fields(self):
        state = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": "export function generateId(): string {\n  return crypto.randomUUID();\n}",
            "generated_tests": "",
            "refined_ticket": {
                "requirements": ["generate a unique id", "return as string"],
            },
        }
        result = score_output(state)
        assert "scores" in result
        assert "total" in result
        assert "passed" in result
        assert "threshold" in result
        assert "reasons" in result
        assert isinstance(result["scores"], dict)
        assert isinstance(result["total"], (int, float))

    def test_score_output_then_gate_check(self):
        """score_output -> gate_check works in sequence."""
        state = {
            "url": "https://github.com/o/r/issues/1",
            "generated_code": "export function hello(): string { return 'world'; }",
            "generated_tests": "",
            "refined_ticket": {"requirements": ["say hello"]},
        }
        ev = score_output(state)
        passed, reason = gate_check(ev)
        assert isinstance(passed, bool)
        assert isinstance(reason, str)


class TestRubricStore:
    """RubricStore.record() stores eval results as JSONL."""

    def test_record_creates_entry(self):
        tmpdir = tempfile.mkdtemp()
        store_path = os.path.join(tmpdir, "test_rubric.jsonl")
        try:
            store = RubricStore(store_path)
            ev = {
                "scores": {"has_actionable_output": 0.9},
                "total": 0.9, "passed": True, "threshold": 0.7, "reasons": [],
            }
            store.record(ev)
            entries = store._read_all()
            assert len(entries) == 1
            assert entries[0]["total"] == 0.9
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_record_multiple_entries(self):
        tmpdir = tempfile.mkdtemp()
        store_path = os.path.join(tmpdir, "test_rubric.jsonl")
        try:
            store = RubricStore(store_path)
            for score in [0.3, 0.5, 0.9]:
                store.record({
                    "scores": {"total": score},
                    "total": score, "passed": score >= 0.7,
                    "threshold": 0.7, "reasons": [],
                })
            entries = store._read_all()
            assert len(entries) == 3
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_history_returns_last_n(self):
        tmpdir = tempfile.mkdtemp()
        store_path = os.path.join(tmpdir, "test_rubric.jsonl")
        try:
            store = RubricStore(store_path)
            for i in range(5):
                store.record({"total": float(i), "passed": False, "scores": {}})
            history = store.get_history(3)
            assert len(history) == 3
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestRegressionTracker:
    """RegressionTracker saves baselines and detects quality changes."""

    def _cleanup(self, tmpdir):
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_save_baseline_on_pass(self):
        tmpdir = tempfile.mkdtemp()
        baselines_path = os.path.join(tmpdir, "test_baselines.json")
        try:
            tracker = RegressionTracker(baselines_path)
            ev = {
                "scores": {"has_actionable_output": 0.9, "structural_integrity": 0.8,
                           "requirement_coverage": 0.7, "test_validation": 0.9},
                "total": 0.825, "passed": True, "threshold": 0.7, "reasons": [],
            }
            tracker.save_baseline(ev)
            loaded = tracker.load_baseline()
            assert loaded is not None
            assert loaded["total"] == 0.825
        finally:
            self._cleanup(tmpdir)

    def test_check_regression_no_baseline(self):
        tmpdir = tempfile.mkdtemp()
        baselines_path = os.path.join(tmpdir, "test_baselines.json")
        try:
            tracker = RegressionTracker(baselines_path)
            ev = {
                "scores": {"has_actionable_output": 0.5},
                "total": 0.5, "passed": False, "threshold": 0.7, "reasons": [],
            }
            result = tracker.check_regression(ev)
            assert result["has_baseline"] is False
        finally:
            self._cleanup(tmpdir)

    def test_check_regression_detects_regression(self):
        tmpdir = tempfile.mkdtemp()
        baselines_path = os.path.join(tmpdir, "test_baselines.json")
        try:
            tracker = RegressionTracker(baselines_path)
            tracker.save_baseline({
                "scores": {"has_actionable_output": 0.9},
                "total": 0.9, "passed": True, "threshold": 0.7, "reasons": [],
            })
            ev = {
                "scores": {"has_actionable_output": 0.3},
                "total": 0.3, "passed": False, "threshold": 0.7, "reasons": [],
            }
            result = tracker.check_regression(ev)
            assert result["has_baseline"] is True
            assert result["regressed"] is True
        finally:
            self._cleanup(tmpdir)

    def test_check_regression_no_regression_when_improved(self):
        tmpdir = tempfile.mkdtemp()
        baselines_path = os.path.join(tmpdir, "test_baselines.json")
        try:
            tracker = RegressionTracker(baselines_path)
            tracker.save_baseline({
                "scores": {"has_actionable_output": 0.5},
                "total": 0.5, "passed": False, "threshold": 0.7, "reasons": [],
            })
            ev = {
                "scores": {"has_actionable_output": 0.9},
                "total": 0.9, "passed": True, "threshold": 0.7, "reasons": [],
            }
            result = tracker.check_regression(ev)
            assert result["has_baseline"] is True
            assert result["regressed"] is False
        finally:
            self._cleanup(tmpdir)

    def test_save_if_improved_saves_when_higher(self):
        tmpdir = tempfile.mkdtemp()
        baselines_path = os.path.join(tmpdir, "test_baselines.json")
        try:
            tracker = RegressionTracker(baselines_path)
            baseline_ev = {
                "scores": {"has_actionable_output": 0.5},
                "total": 0.5,
                "passed": False,
                "threshold": 0.7,
                "reasons": [],
            }
            tracker.save_baseline(baseline_ev)
            improved_ev = {
                "scores": {"has_actionable_output": 0.9},
                "total": 0.9,
                "passed": True,
                "threshold": 0.7,
                "reasons": [],
            }
            saved = tracker.save_if_improved(improved_ev)
            assert saved is True
            loaded = tracker.load_baseline()
            assert loaded["total"] == 0.9
        finally:
            self._cleanup(tmpdir)
