"""
Production Monitor — continuous quality monitoring.

Implements the production-side eval loop from fix_the_slop.md:
- Periodic sampling and scoring of eval results
- Degradation detection: recent avg >10% below historical average
- Threshold-based alerting
- Feedback loop: user-flagged failures become permanent data points
"""

import os
from datetime import datetime
from typing import Optional

from .eval_rubric import RubricStore, DEFAULT_STORE_PATH


class ProductionMonitor:
    """Continuous quality monitor backed by a RubricStore."""

    def __init__(self, eval_store_path: Optional[str] = None):
        self.store = RubricStore(path=eval_store_path)

    def sample_and_score(self) -> dict:
        """Load all records and return aggregate quality stats."""
        entries = self.store._read_all()
        if not entries:
            return {
                "total_runs": 0,
                "pass_rate": 0.0,
                "avg_score": 0.0,
                "per_criterion_avg": {},
            }

        totals = [e.get("total", 0) for e in entries]
        passed_count = sum(1 for e in entries if e.get("passed", False))
        avg_score = round(sum(totals) / len(totals), 4)

        criterion_sums: dict[str, float] = {}
        criterion_counts: dict[str, int] = {}
        for entry in entries:
            scores = entry.get("scores", {})
            for name, val in scores.items():
                criterion_sums[name] = criterion_sums.get(name, 0.0) + float(val)
                criterion_counts[name] = criterion_counts.get(name, 0) + 1

        per_criterion_avg = {
            name: round(criterion_sums[name] / criterion_counts[name], 4)
            for name in criterion_sums
        }

        return {
            "total_runs": len(entries),
            "pass_rate": round(passed_count / len(entries), 4),
            "avg_score": avg_score,
            "per_criterion_avg": per_criterion_avg,
        }

    def check_degradation(self, window_size: int = 10) -> tuple:
        """Compare recent window against historical average.

        Returns (is_degrading, message).
        """
        entries = self.store._read_all()
        if len(entries) < 2:
            return False, ""

        recent = entries[-window_size:]
        historical = entries[:-window_size] if len(entries) > window_size else entries[: len(entries) // 2]

        if not recent or not historical:
            return False, ""

        recent_avg = sum(e.get("total", 0) for e in recent) / len(recent)
        historical_avg = sum(e.get("total", 0) for e in historical) / len(historical)

        if historical_avg == 0:
            return False, ""

        drop_pct = (historical_avg - recent_avg) / historical_avg
        is_degrading = drop_pct > 0.10

        if is_degrading:
            msg = (
                f"[DEGRADATION] Recent {len(recent)} runs avg {recent_avg:.4f} "
                f"vs historical {len(historical)} runs avg {historical_avg:.4f} "
                f"({drop_pct:.1%} drop — threshold 10%)"
            )
            return True, msg

        return False, ""

    def get_quality_report(self) -> dict:
        """Comprehensive quality statistics including trend."""
        stats = self.sample_and_score()
        entries = self.store._read_all()

        if len(entries) >= 10:
            recent_5 = [e.get("total", 0) for e in entries[-5:]]
            prior_5 = [e.get("total", 0) for e in entries[-10:-5]]
            recent_avg = sum(recent_5) / len(recent_5)
            prior_avg = sum(prior_5) / len(prior_5)
            if recent_avg < prior_avg * 0.95:
                trend = "degrading"
            elif recent_avg > prior_avg * 1.05:
                trend = "improving"
            else:
                trend = "stable"
        elif len(entries) >= 2:
            trend = self.store.get_trend().get("direction", "stable")
        else:
            trend = "insufficient_data"

        recent_entries = entries[-10:]
        criterion_recent: dict[str, list[float]] = {}
        for entry in recent_entries:
            for name, val in entry.get("scores", {}).items():
                criterion_recent.setdefault(name, []).append(float(val))

        criterion_detail = {}
        for name, vals in criterion_recent.items():
            criterion_detail[name] = {
                "recent_avg": round(sum(vals) / len(vals), 4),
                "recent_min": round(min(vals), 4),
                "recent_max": round(max(vals), 4),
            }

        return {
            "total_runs": stats["total_runs"],
            "pass_rate": stats["pass_rate"],
            "avg_score": stats["avg_score"],
            "per_criterion_avg": stats["per_criterion_avg"],
            "trend": trend,
            "criterion_detail": criterion_detail,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }


class ThresholdAlerter:
    """Alert when scores drop below a configurable threshold."""

    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold

    def check(self, score_result: dict) -> str:
        """Return alert message if below threshold, empty string if OK."""
        total = score_result.get("total", 0)
        if total < self.threshold:
            return self.format_alert(score_result)
        return ""

    def format_alert(self, score_result: dict, context: str = "") -> str:
        """Human-readable alert with specific failure reasons."""
        total = score_result.get("total", 0)
        scores = score_result.get("scores", {})
        reasons = score_result.get("reasons", [])

        lines = [
            f"[ALERT] Quality score {total:.4f} below threshold {self.threshold}",
        ]
        if context:
            lines.append(f"  Context: {context}")

        if scores:
            worst = sorted(scores.items(), key=lambda x: x[1])
            lines.append("  Criterion scores:")
            for name, val in worst:
                flag = " <-- LOW" if val < 0.5 else ""
                lines.append(f"    {name}: {val:.4f}{flag}")

        if reasons:
            lines.append("  Reasons:")
            for r in reasons:
                lines.append(f"    - {r}")

        return "\n".join(lines)


def run_production_check(eval_store_path: Optional[str] = None) -> dict:
    """Cron-compatible production check. Returns structured dict.

    Returns:
        {
            "status": "healthy" | "degrading",
            "report": {full quality report},
            "alert": alert message or None,
            "formatted_alert": human-readable alert or None,
            "timestamp": ISO timestamp,
        }
    """
    monitor = ProductionMonitor(eval_store_path=eval_store_path)
    report = monitor.get_quality_report()
    is_degrading, message = monitor.check_degradation()

    result = {
        "status": "degrading" if is_degrading else "healthy",
        "report": report,
        "alert": message if is_degrading else None,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if is_degrading:
        alerter = ThresholdAlerter()
        result["formatted_alert"] = alerter.format_alert(
            {"total": report["avg_score"], "scores": report["per_criterion_avg"]},
            context=message,
        )

    return result


def close_the_loop(feedback: dict) -> None:
    """Write a user-flagged failure into the RubricStore.

    Called when a user marks output as bad. The feedback dict should contain
    at minimum a 'scores' dict and 'total' field.
    """
    store_path = feedback.pop("_store_path", None)
    store = RubricStore(path=store_path or os.getenv("EVAL_STORE_PATH", DEFAULT_STORE_PATH))

    entry = {
        "flagged": True,
        "flagged_at": datetime.utcnow().isoformat() + "Z",
        **feedback,
    }
    store.record(entry)
