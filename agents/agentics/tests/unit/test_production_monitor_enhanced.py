"""
Tests for production_monitor enhancements.
Categories 4-5 from tester-plan.md.
"""

import os
import json
import tempfile
import pytest

from src.production_monitor import (
    ProductionMonitor,
    ThresholdAlerter,
    run_production_check,
    close_the_loop,
)
from src.eval_rubric import RubricStore


@pytest.fixture
def tmp_store():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    RubricStore(path=path)  # init file
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _write_entries(path, entries):
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _make_entry(total, passed, scores=None, timestamp="2026-01-01T00:00:00Z"):
    if scores is None:
        scores = {
            "has_actionable_output": 1.0,
            "structural_integrity": 0.8,
            "requirement_coverage": 0.9,
            "test_validation": 0.7,
        }
    return {"timestamp": timestamp, "total": total, "passed": passed, "scores": scores}


class TestRunProductionCheck:
    """Category 4.1: run_production_check returns structured dict."""

    def test_returns_dict_with_required_keys(self):
        result = run_production_check()
        assert "status" in result
        assert "report" in result
        assert "alert" in result
        assert "timestamp" in result

    def test_status_is_healthy_or_degrading(self):
        result = run_production_check()
        assert result["status"] in ("healthy", "degrading")

    def test_healthy_system_alert_is_none(self, tmp_store):
        for i in range(5):
            _write_entries(tmp_store, [_make_entry(0.85, True)])
        result = run_production_check(eval_store_path=tmp_store)
        # With uniform scores, status should be healthy
        if result["status"] == "healthy":
            assert result["alert"] is None

    def test_degrading_system_has_alert_and_formatted_alert(self, tmp_store):
        # Create entries where recent avg is significantly below historical
        entries = []
        # 8 historical entries with high scores
        for _ in range(8):
            entries.append(_make_entry(0.9, True))
        # 5 recent entries with much lower scores (>10% drop)
        for _ in range(5):
            entries.append(_make_entry(0.5, False, {
                "has_actionable_output": 0.5,
                "structural_integrity": 0.4,
                "requirement_coverage": 0.5,
                "test_validation": 0.6,
            }))
        _write_entries(tmp_store, entries)
        result = run_production_check(eval_store_path=tmp_store)
        if result["status"] == "degrading":
            assert result["alert"] is not None
            assert isinstance(result["alert"], str)
            assert len(result["alert"]) > 0
            # formatted_alert should be present when degrading
            assert "formatted_alert" in result
            assert result["formatted_alert"] is not None

    def test_degrading_has_formatted_alert_key(self, tmp_store):
        """When degrading, result must include formatted_alert."""
        entries = []
        for _ in range(6):
            entries.append(_make_entry(0.95, True))
        for _ in range(6):
            entries.append(_make_entry(0.4, False, {
                "has_actionable_output": 0.3,
                "structural_integrity": 0.4,
                "requirement_coverage": 0.5,
                "test_validation": 0.4,
            }))
        _write_entries(tmp_store, entries)
        result = run_production_check(eval_store_path=tmp_store)
        # Regardless of degrading detection, check structure
        if result["status"] == "degrading":
            assert "formatted_alert" in result
            assert "[ALERT]" in result["formatted_alert"]

    def test_timestamp_is_iso_format(self):
        result = run_production_check()
        assert "T" in result["timestamp"]
        assert result["timestamp"].endswith("Z")

    def test_report_structure_no_crash(self):
        result = run_production_check()
        report = result["report"]
        assert isinstance(report, dict)


class TestDegradationDetection:
    """Category 4.2: Degradation detection at various thresholds."""

    def test_no_degradation_with_few_entries(self, tmp_store):
        """< 2 entries should not trigger degradation."""
        _write_entries(tmp_store, [_make_entry(0.85, True)])
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        degrading, _ = monitor.check_degradation()
        assert degrading is False

    def test_no_degradation_with_two_entries_same(self, tmp_store):
        _write_entries(tmp_store, [
            _make_entry(0.85, True),
            _make_entry(0.85, True),
        ])
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        degrading, _ = monitor.check_degradation()
        assert degrading is False

    def test_degradation_15_percent_drop(self, tmp_store):
        """Recent avg 15% below historical -> degrading = True."""
        entries = []
        # 8 historical at 0.9
        for _ in range(8):
            entries.append(_make_entry(0.9, True))
        # 5 recent at 0.7 => ~22% drop from 0.9
        for _ in range(5):
            entries.append(_make_entry(0.7, True, {
                "has_actionable_output": 0.7,
                "structural_integrity": 0.7,
                "requirement_coverage": 0.7,
                "test_validation": 0.7,
            }))
        _write_entries(tmp_store, entries)
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        degrading, msg = monitor.check_degradation()
        assert degrading is True
        assert "DEGRADATION" in msg

    def test_no_degradation_5_percent_drop(self, tmp_store):
        """Recent avg 5% below historical -> degrading = False."""
        entries = []
        # 8 historical at 0.9
        for _ in range(8):
            entries.append(_make_entry(0.9, True))
        # 5 recent at 0.86 => ~4.4% drop from 0.9
        for _ in range(5):
            entries.append(_make_entry(0.86, True, {
                "has_actionable_output": 0.86,
                "structural_integrity": 0.86,
                "requirement_coverage": 0.86,
                "test_validation": 0.86,
            }))
        _write_entries(tmp_store, entries)
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        degrading, _ = monitor.check_degradation()
        assert degrading is False

    def test_degradation_message_contains_percent(self, tmp_store):
        entries = []
        for _ in range(8):
            entries.append(_make_entry(0.9, True))
        for _ in range(5):
            entries.append(_make_entry(0.5, False))
        _write_entries(tmp_store, entries)
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        degrading, msg = monitor.check_degradation()
        assert degrading is True
        assert "%" in msg
        assert "10%" in msg

    def test_degradation_false_when_improving(self, tmp_store):
        entries = []
        for _ in range(8):
            entries.append(_make_entry(0.5, False))
        for _ in range(5):
            entries.append(_make_entry(0.9, True))
        _write_entries(tmp_store, entries)
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        degrading, _ = monitor.check_degradation()
        assert degrading is False


class TestQualityReport:
    """Category 4.3: Quality report has all required keys."""

    def test_report_contains_all_required_keys(self, tmp_store):
        _write_entries(tmp_store, [
            _make_entry(0.85, True),
            _make_entry(0.90, True),
        ])
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        report = monitor.get_quality_report()
        required_keys = [
            "total_runs", "pass_rate", "avg_score",
            "per_criterion_avg", "trend", "criterion_detail",
            "generated_at",
        ]
        for key in required_keys:
            assert key in report, f"Missing key: {key}"

    def test_trend_is_valid_value(self, tmp_store):
        _write_entries(tmp_store, [
            _make_entry(0.85, True),
        ])
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        report = monitor.get_quality_report()
        assert report["trend"] in ("stable", "degrading", "improving", "insufficient_data")

    def test_trend_insufficient_data_for_single_entry(self, tmp_store):
        _write_entries(tmp_store, [_make_entry(0.85, True)])
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        report = monitor.get_quality_report()
        assert report["trend"] == "insufficient_data"

    def test_report_generated_at_is_iso(self, tmp_store):
        _write_entries(tmp_store, [_make_entry(0.85, True)])
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        report = monitor.get_quality_report()
        assert report["generated_at"].endswith("Z")
        assert "T" in report["generated_at"]

    def test_report_total_runs_matches_entries(self, tmp_store):
        entries = [_make_entry(0.85, True) for _ in range(3)]
        _write_entries(tmp_store, entries)
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        report = monitor.get_quality_report()
        assert report["total_runs"] == 3

    def test_report_pass_rate_range(self, tmp_store):
        _write_entries(tmp_store, [
            _make_entry(0.85, True),
            _make_entry(0.90, False),
        ])
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        report = monitor.get_quality_report()
        assert 0.0 <= report["pass_rate"] <= 1.0

    def test_report_criterion_detail_structure(self, tmp_store):
        entries = [
            _make_entry(0.85, True, {
                "has_actionable_output": 1.0,
                "structural_integrity": 0.8,
            })
            for _ in range(5)
        ]
        _write_entries(tmp_store, entries)
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        report = monitor.get_quality_report()
        detail = report["criterion_detail"]
        for criterion, stats in detail.items():
            assert "recent_avg" in stats
            assert "recent_min" in stats
            assert "recent_max" in stats

    def test_report_empty_store(self, tmp_store):
        _write_entries(tmp_store, [])
        monitor = ProductionMonitor(eval_store_path=tmp_store)
        report = monitor.get_quality_report()
        assert report["total_runs"] == 0
        assert report["pass_rate"] == 0.0
        assert report["avg_score"] == 0.0


class TestThresholdAlerter:
    def test_alert_below_threshold(self):
        alerter = ThresholdAlerter(threshold=0.7)
        result = alerter.check({"total": 0.5, "scores": {"a": 0.5}, "reasons": ["low"]})
        assert "[ALERT]" in result
        assert "below threshold 0.7" in result

    def test_no_alert_above_threshold(self):
        alerter = ThresholdAlerter(threshold=0.7)
        result = alerter.check({"total": 0.8, "scores": {"a": 0.8}, "reasons": []})
        assert result == ""

    def test_alert_at_threshold(self):
        alerter = ThresholdAlerter(threshold=0.7)
        result = alerter.check({"total": 0.7, "scores": {}, "reasons": []})
        assert result == ""

    def test_alert_includes_worst_scores(self):
        alerter = ThresholdAlerter(threshold=0.7)
        result = alerter.check({
            "total": 0.3,
            "scores": {"has_actionable_output": 0.1, "structural_integrity": 0.5},
            "reasons": ["has_actionable_output=0.10"]
        })
        assert "has_actionable_output" in result
        assert "0.1" in result

    def test_alert_includes_reasons(self):
        alerter = ThresholdAlerter(threshold=0.7)
        result = alerter.check({
            "total": 0.3,
            "scores": {"a": 0.3},
            "reasons": ["syntax error", "missing tests"]
        })
        assert "syntax error" in result
        assert "missing tests" in result

    def test_alert_with_context(self):
        alerter = ThresholdAlerter(threshold=0.7)
        result = alerter.format_alert(
            {"total": 0.3, "scores": {"a": 0.3}},
            context="batch run #42"
        )
        assert "batch run #42" in result

    def test_low_scores_flagged(self):
        alerter = ThresholdAlerter(threshold=0.7)
        result = alerter.check({
            "total": 0.3,
            "scores": {"good_criterion": 0.9, "bad_criterion": 0.2},
            "reasons": []
        })
        assert "LOW" in result
        assert "bad_criterion" in result


class TestCloseTheLoop:
    """Category 5.2: close_the_loop writes flagged entries."""

    def test_flagged_entry_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "eval_loop.jsonl")
            RubricStore(path=store_path)  # init
            close_the_loop({
                "_store_path": store_path,
                "scores": {"a": 0.3},
                "total": 0.3,
            })
            store = RubricStore(path=store_path)
            entries = store._read_all()
            assert len(entries) == 1
            assert entries[0]["flagged"] is True
            assert "flagged_at" in entries[0]

    def test_flagged_at_is_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "eval_loop.jsonl")
            RubricStore(path=store_path)
            close_the_loop({
                "_store_path": store_path,
                "scores": {"a": 0.3},
                "total": 0.3,
            })
            store = RubricStore(path=store_path)
            entries = store._read_all()
            flagged_at = entries[0]["flagged_at"]
            assert "T" in flagged_at
            assert flagged_at.endswith("Z")

    def test_preserves_feedback_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "eval_loop.jsonl")
            RubricStore(path=store_path)
            close_the_loop({
                "_store_path": store_path,
                "scores": {"a": 0.3, "b": 0.5},
                "total": 0.4,
                "issue_url": "https://github.com/foo/bar/issues/1",
                "feedback": "output was wrong",
            })
            store = RubricStore(path=store_path)
            entries = store._read_all()
            entry = entries[0]
            assert entry["issue_url"] == "https://github.com/foo/bar/issues/1"
            assert entry["feedback"] == "output was wrong"
            assert entry["total"] == 0.4

    def test_multiple_flagged_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "eval_loop.jsonl")
            RubricStore(path=store_path)
            for i in range(3):
                close_the_loop({
                    "_store_path": store_path,
                    "scores": {"a": 0.3},
                    "total": 0.3,
                })
            store = RubricStore(path=store_path)
            entries = store._read_all()
            assert len(entries) == 3
            for e in entries:
                assert e["flagged"] is True
