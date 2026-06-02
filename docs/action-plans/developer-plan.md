# Developer Action Plan

## Implementation Order

Tasks are ordered by dependency. Each task has a kanban card ID.

---

## TASK-01: Fix structural_integrity heuristic in eval_rubric.py

**File**: `agents/agentics/src/eval_rubric.py`

**Problem**: The current heuristic gives +1 for nearly every line (even garbage), making scores artificially high.

**Changes**:
```python
# BEFORE (lines 44-66): Nearly every line passes
# All non-empty lines get +1, so score is always ~0.9

# AFTER: Stricter checks
def structural_integrity(state: dict) -> float:
    code = (state.get("generated_code") or "").strip()
    if not code:
        return 0.0
    lines = code.split("\n")
    checks = []
    
    # Check 1: Balanced braces (0.2 weight)
    checks.append(("braces_balanced", _braces_balanced(code), 0.2))
    
    # Check 2: Balanced parentheses (0.2 weight)
    checks.append(("parens_balanced", _parens_balanced(code), 0.2))
    
    # Check 3: No broken clusters (0.1 weight)
    checks.append(("no_broken_clusters", not re.search(r"}{5,}", code), 0.1))
    
    # Check 4: Line-level syntax validity (0.5 weight)
    valid_lines = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Valid TS line patterns
        if re.match(r'^(export\s+)?function\s+\w+', stripped): valid_lines += 1
        elif re.match(r'^(const|let|var)\s+\w+', stripped): valid_lines += 1
        elif re.match(r'^return\s+', stripped): valid_lines += 1
        elif re.match(r'^[})\];]+$', stripped): valid_lines += 1
        elif re.match(r'^\w+\([^)]*\)\s*{?$', stripped): valid_lines += 1
        elif re.match(r'^if\s*\(', stripped): valid_lines += 1
        elif re.match(r'^(//|/\*|\*)', stripped): valid_lines += 1
        elif re.match(r'^[{]$', stripped): valid_lines += 1
        elif len(stripped) > 200: continue  # Penalize very long lines
        elif re.match(r'^[\w.,;:{}[\]()=+\-*/<>!&|?~]+$', stripped): valid_lines += 1
    line_score = valid_lines / max(len([l for l in lines if l.strip()]), 1)
    checks.append(("line_syntax", line_score, 0.5))
    
    score = sum(weight for (name, passed, weight) in checks if (passed is True or isinstance(passed, float) and passed > 0.5))
    return round(min(score, 1.0), 4)
```

**Tests**: Update `test_exceptions_unit.py` to cover new structural_integrity logic

---

## TASK-02: Add RegressionTracker to eval_rubric.py

**File**: `agents/agentics/src/eval_rubric.py`

**New class**:
```python
class RegressionTracker:
    """Compares current eval scores against a saved baseline."""
    
    def __init__(self, baseline_path: str = "/tmp/eval_baseline.json"):
        self.baseline_path = baseline_path
    
    def save_baseline(self, scores: dict):
        """Save current scores as the new baseline."""
        import json
        from datetime import datetime
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "scores": scores["scores"],
            "total": scores["total"],
        }
        os.makedirs(os.path.dirname(self.baseline_path) or ".", exist_ok=True)
        with open(self.baseline_path, "w") as f:
            json.dump(entry, f, indent=2)
    
    def load_baseline(self) -> dict | None:
        """Load saved baseline scores."""
        if not os.path.exists(self.baseline_path):
            return None
        with open(self.baseline_path) as f:
            return json.load(f)
    
    def check_regression(self, current_scores: dict) -> dict:
        """Compare current scores against baseline. Returns regression report."""
        baseline = self.load_baseline()
        if not baseline:
            return {"has_baseline": False, "regressed": False, "deltas": {}}
        
        deltas = {}
        regressed = False
        for criterion, current_val in current_scores.get("scores", {}).items():
            baseline_val = baseline.get("scores", {}).get(criterion, 0)
            delta = current_val - baseline_val
            deltas[criterion] = round(delta, 4)
            if delta < -0.1:  # 10% regression threshold
                regressed = True
        
        total_delta = current_scores.get("total", 0) - baseline.get("total", 0)
        
        return {
            "has_baseline": True,
            "regressed": regressed,
            "deltas": deltas,
            "total_delta": round(total_delta, 4),
            "baseline_total": baseline.get("total", 0),
            "current_total": current_scores.get("total", 0),
        }
```

---

## TASK-03: Create test_suite.py — Gold Standard Management

**File**: `agents/agentics/src/test_suite.py` (NEW)

```python
"""Gold standard test case management for regression testing."""

import json
import os
from datetime import datetime
from typing import Optional


class GoldStandardSuite:
    """Manages gold standard test cases: input + expected output pairs."""
    
    def __init__(self, suite_path: str = "/tmp/gold_standard_suite.json"):
        self.suite_path = suite_path
        self._ensure_file()
    
    def _ensure_file(self):
        if not os.path.exists(self.suite_path):
            os.makedirs(os.path.dirname(self.suite_path) or ".", exist_ok=True)
            with open(self.suite_path, "w") as f:
                json.dump({"cases": [], "version": "1.0"}, f)
    
    def add_case(self, input_data: str, expected_output: str, 
                 criteria_thresholds: Optional[dict] = None) -> str:
        """Add a gold standard test case. Returns case_id."""
        cases = self._load_all()
        case_id = f"gold_{len(cases['cases']):04d}"
        entry = {
            "id": case_id,
            "input": input_data,
            "expected_output": expected_output,
            "criteria_thresholds": criteria_thresholds or {
                "has_actionable_output": 1.0,
                "structural_integrity": 0.8,
                "requirement_coverage": 0.7,
                "test_validation": 0.7,
            },
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        cases["cases"].append(entry)
        self._save_all(cases)
        return case_id
    
    def get_case(self, case_id: str) -> Optional[dict]:
        cases = self._load_all()
        for c in cases["cases"]:
            if c["id"] == case_id:
                return c
        return None
    
    def get_all_cases(self) -> list:
        return self._load_all()["cases"]
    
    def remove_case(self, case_id: str) -> bool:
        cases = self._load_all()
        original_len = len(cases["cases"])
        cases["cases"] = [c for c in cases["cases"] if c["id"] != case_id]
        self._save_all(cases)
        return len(cases["cases"]) < original_len
    
    def _load_all(self) -> dict:
        with open(self.suite_path) as f:
            return json.load(f)
    
    def _save_all(self, data: dict):
        with open(self.suite_path, "w") as f:
            json.dump(data, f, indent=2)
```

---

## TASK-04: Restructure workflow.py — Eval Gate Before Integration

**File**: `agents/agentics/src/workflow.py`

**Key changes**:

1. Move eval scoring BEFORE code integration:
```python
# In _node_generate_code_tests, restructure the flow:

# BEFORE: generate → integrate → eval (wrong!)
# AFTER:  generate → eval → integrate (correct!)

# After generating gen_code and gen_test_code:
# Step 1: Score BEFORE integration
state_for_eval = {**state, "generated_code": gen_code, "generated_tests": gen_test_code}
ev = score_output(state_for_eval)
passed, gate_reason = gate_check(ev)

# Step 2: Only integrate if eval passed
if passed:
    # ... integration code (import + addCommand) ...
    state["integrated"] = True
else:
    state["integrated"] = False
    log_info("generate", f"Eval gate blocked integration: {gate_reason}")
    # Still record the failure for retry context
    state["failed_criteria"] = record_failure(state_for_eval, ev).get("failed_criteria", [])

# Step 3: Save baseline if eval passed
if passed:
    from .eval_rubric import RegressionTracker
    tracker = RegressionTracker()
    tracker.save_baseline(ev)
    state["regression_check"] = {"passed": True}
else:
    tracker = RegressionTracker()
    regression = tracker.check_regression(ev)
    state["regression_check"] = regression
```

2. Remove redundant eval from `_node_test` (keep only the jest run)

3. Add conditional routing via LangGraph edges

---

## TASK-05: Fix agentics.py — Regression Runner + Feedback Loop

**File**: `agents/agentics/src/agentics.py`

**Changes**:

```python
async def run_regression_suite(self) -> dict:
    """Run all gold standard cases through the workflow and score them."""
    from .test_suite import GoldStandardSuite
    from .eval_rubric import RegressionTracker
    
    suite = GoldStandardSuite()
    tracker = RegressionTracker()
    cases = suite.get_all_cases()
    
    if not cases:
        return {"status": "no_cases", "total": 0, "passed": 0, "failed": 0}
    
    results = []
    for case in cases:
        # Run workflow on the gold standard input
        result = await self.workflow.process_issue(case["input"])
        eval_scores = result.get("eval_scores", {})
        
        # Check against case-specific thresholds
        thresholds = case.get("criteria_thresholds", {})
        case_passed = True
        for criterion, threshold in thresholds.items():
            if eval_scores.get(criterion, 0) < threshold:
                case_passed = False
                break
        
        results.append({
            "case_id": case["id"],
            "passed": case_passed,
            "scores": eval_scores,
        })
    
    passed_count = sum(1 for r in results if r["passed"])
    return {
        "status": "complete",
        "total": len(cases),
        "passed": passed_count,
        "failed": len(cases) - passed_count,
        "results": results,
    }
```

Fix `record_feedback`:
```python
def record_feedback(self, issue_url: str, feedback: str) -> None:
    """Record user feedback and close the eval loop."""
    if not feedback or not feedback.strip():
        log_info(__name__, "Empty feedback received, ignoring")
        return
    
    entries = self.rubric_store._read_all()
    for entry in reversed(entries):
        if entry.get("issue_url") == issue_url:
            entry["feedback"] = feedback
            entry["flagged"] = True
            entry["flagged_at"] = datetime.utcnow().isoformat() + "Z"
            close_the_loop(entry)
            log_info(__name__, f"Feedback recorded for {issue_url}")
            return
    
    log_info(__name__, f"No matching entry found for {issue_url}")
```

---

## TASK-06: Enhance production_monitor.py

**File**: `agents/agentics/src/production_monitor.py`

**Changes**:

1. Fix `run_production_check` to return structured dict:
```python
def run_production_check(eval_store_path: Optional[str] = None) -> dict:
    """Cron-compatible production check. Returns structured dict."""
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
            context=message
        )
    
    return result
```

---

## TASK-07: Update state.py with new fields

**File**: `agents/agentics/src/state.py`

**Add**:
```python
class State(TypedDict, total=False):
    # ... existing fields ...
    
    # Regression testing
    regression_check: dict
    baseline_score: float
    regression_score: float
    
    # Integration gate
    integrated: bool
    integration_blocked_reason: str
    
    # Production monitoring
    quality_report: dict
```

---

## TASK-08: Write Tests for All Changes

**Files**: New and updated test files in `agents/agentics/tests/unit/`

New test files:
- `test_eval_rubric_enhanced.py` — Tests for improved structural_integrity, RegressionTracker
- `test_regression.py` — Tests for RegressionTracker
- `test_test_suite.py` — Tests for GoldStandardSuite
- `test_production_monitor_enhanced.py` — Tests for updated production_monitor

Updated test files:
- `test_workflow_unit.py` — Update for new eval gate ordering
- `test_workflow_edge_cases.py` — Add edge cases for regression, gold standard

---

## Verification Steps

After all changes:
1. Run `make test-agents-unit-mock` — All existing + new unit tests pass
2. Run `make lint-python` — No lint errors
3. Run `make test-agents-unit` — Integration with Ollama works
4. Verify eval gate blocks integration when score < 0.7
5. Verify regression detection triggers on 10% score drop
6. Verify gold standard suite CRUD operations
7. Verify production monitoring returns structured dict
