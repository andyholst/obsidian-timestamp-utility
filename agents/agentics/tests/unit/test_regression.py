"""Tests for RegressionTracker: save/load, regression detection at various thresholds."""

import os
import json
import pytest

from src.eval_rubric import RegressionTracker


@pytest.fixture
def tmp_baseline(tmp_path):
    return str(tmp_path / "eval_baseline.json")


@pytest.fixture
def tracker(tmp_baseline):
    return RegressionTracker(baseline_path=tmp_baseline)


@pytest.fixture
def sample_scores():
    return {
        "scores": {"has_actionable_output": 1.0, "structural_integrity": 0.85, "requirement_coverage": 0.9, "test_validation": 0.75},
        "total": 0.875,
    }


class TestRegressionTrackerNoBaseline:
    def test_load_baseline_returns_none_when_missing(self, tracker):
        assert tracker.load_baseline() is None

    def test_check_regression_no_baseline(self, tracker, sample_scores):
        result = tracker.check_regression(sample_scores)
        assert result["has_baseline"] is False
        assert result["regressed"] is False
        assert result["deltas"] == {}


class TestRegressionTrackerSaveLoad:
    def test_save_then_load_returns_same_data(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        loaded = tracker.load_baseline()
        assert loaded is not None
        assert loaded["scores"] == sample_scores["scores"]
        assert loaded["total"] == sample_scores["total"]
        assert "timestamp" in loaded

    def test_save_creates_file(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        assert os.path.exists(tracker.baseline_path)

    def test_save_creates_parent_directories(self, tmp_path, sample_scores):
        deep = str(tmp_path / "deep" / "nested" / "baseline.json")
        RegressionTracker(baseline_path=deep).save_baseline(sample_scores)
        assert os.path.exists(deep)

    def test_save_overwrites_existing(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        new_scores = {"scores": {"a": 0.5, "b": 0.5, "c": 0.5, "d": 0.5}, "total": 0.5}
        tracker.save_baseline(new_scores)
        assert tracker.load_baseline()["total"] == 0.5

    def test_load_baseline_returns_dict(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        loaded = tracker.load_baseline()
        assert isinstance(loaded, dict)
        assert "scores" in loaded and "total" in loaded


class TestRegressionTrackerRegression:
    def test_no_regression_identical_scores(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        result = tracker.check_regression(sample_scores)
        assert result["has_baseline"] is True
        assert result["regressed"] is False

    def test_no_regression_slight_improvement(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        better = {"scores": {"has_actionable_output": 1.0, "structural_integrity": 0.95, "requirement_coverage": 0.95, "test_validation": 0.85}, "total": 0.9375}
        assert tracker.check_regression(better)["regressed"] is False

    def test_regression_at_15_percent_drop(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        degraded = {"scores": {"has_actionable_output": 1.0, "structural_integrity": 0.70, "requirement_coverage": 0.9, "test_validation": 0.75}, "total": 0.8375}
        result = tracker.check_regression(degraded)
        assert result["regressed"] is True
        assert result["deltas"]["structural_integrity"] == -0.15

    def test_no_regression_at_5_percent_drop(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        slight = {"scores": {"has_actionable_output": 1.0, "structural_integrity": 0.80, "requirement_coverage": 0.9, "test_validation": 0.75}, "total": 0.8625}
        assert tracker.check_regression(slight)["regressed"] is False

    def test_regression_multiple_criteria(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        bad = {"scores": {"has_actionable_output": 1.0, "structural_integrity": 0.50, "requirement_coverage": 0.50, "test_validation": 0.75}, "total": 0.7075}
        result = tracker.check_regression(bad)
        assert result["regressed"] is True
        assert result["deltas"]["structural_integrity"] == -0.35
        assert result["deltas"]["requirement_coverage"] == -0.40

    def test_total_delta_calculated(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        new = {"scores": {"has_actionable_output": 1.0, "structural_integrity": 0.85, "requirement_coverage": 0.9, "test_validation": 0.75}, "total": 0.80}
        result = tracker.check_regression(new)
        assert result["total_delta"] == round(0.80 - 0.875, 4)

    def test_report_contains_totals(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        result = tracker.check_regression(sample_scores)
        assert result["baseline_total"] == 0.875
        assert result["current_total"] == 0.875

    def test_boundary_exactly_10_pct_no_regression(self, tracker):
        baseline = {"scores": {"has_actionable_output": 1.0, "structural_integrity": 0.85, "requirement_coverage": 0.9, "test_validation": 0.75}, "total": 0.875}
        tracker.save_baseline(baseline)
        current = {"scores": {"has_actionable_output": 1.0, "structural_integrity": 0.75, "requirement_coverage": 0.9, "test_validation": 0.75}, "total": 0.85}
        assert tracker.check_regression(current)["regressed"] is False

    def test_just_over_10_pct_triggers(self, tracker):
        baseline = {"scores": {"has_actionable_output": 1.0, "structural_integrity": 0.85, "requirement_coverage": 0.9, "test_validation": 0.75}, "total": 0.875}
        tracker.save_baseline(baseline)
        current = {"scores": {"has_actionable_output": 1.0, "structural_integrity": 0.74, "requirement_coverage": 0.9, "test_validation": 0.75}, "total": 0.8475}
        result = tracker.check_regression(current)
        assert result["deltas"]["structural_integrity"] < -0.1
        assert result["regressed"] is True

    def test_new_criterion_not_in_baseline(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        new = {"scores": {**sample_scores["scores"], "new_criterion": 0.5}, "total": 0.875}
        assert "new_criterion" in tracker.check_regression(new)["deltas"]

    def test_save_if_improved_no_baseline(self, tracker, sample_scores):
        assert tracker.save_if_improved(sample_scores) is True

    def test_save_if_improved_when_better(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        better = {"scores": {**sample_scores["scores"], "structural_integrity": 0.95}, "total": 0.9}
        assert tracker.save_if_improved(better) is True

    def test_save_if_improved_when_worse(self, tracker, sample_scores):
        tracker.save_baseline(sample_scores)
        worse = {"scores": {**sample_scores["scores"], "structural_integrity": 0.50}, "total": 0.7}
        assert tracker.save_if_improved(worse) is False
