# Tester Action Plan

## Test Strategy Overview

The refactor must satisfy the fix_the_slop.md principle: **eval loop = generate → score → catch → fix → re-score → gate**. Tests must verify each stage of this loop.

## Test Categories

### Category 1: Eval Rubric Tests (eval_rubric + regression)

#### Test 1.1: structural_integrity — Stricter Heuristic
- **Input**: Valid TypeScript code with balanced braces and proper syntax
- **Expected**: score >= 0.8
- **Input**: Code with unbalanced braces
- **Expected**: score < 0.3 (braces check fails, line syntax may pass partially)
- **Input**: Empty string
- **Expected**: 0.0
- **Input**: Garbage text (random words, no TS patterns)
- **Expected**: score < 0.3
- **Input**: Code with very long lines (>200 chars)
- **Expected**: Penalized score
- **File**: `test_eval_rubric_enhanced.py::TestStructuralIntegrity`

#### Test 1.2: requirement_coverage — Edge Cases
- **Input**: Empty requirements in ticket
- **Expected**: 0.0 (not 0.5 — changed behavior)
- **Input**: Requirements with only stop words
- **Expected**: 0.0
- **Input**: Requirements fully matched in code
- **Expected**: 1.0
- **Input**: Requirements partially matched
- **Expected**: Fractional score (matched/total)
- **File**: `test_eval_rubric_enhanced.py::TestRequirementCoverage`

#### Test 1.3: RegressionTracker — Save/Load/Compare
- **Test**: Save baseline → load baseline → verify identical
- **Test**: Check regression with identical scores → no regression
- **Test**: Check regression with 15% drop → regressed flag = True
- **Test**: Check regression with 5% drop → regressed flag = False
- **Test**: Check regression with no baseline → has_baseline = False
- **File**: `test_regression.py::TestRegressionTracker`

#### Test 1.4: score_output — Weighted Total
- **Test**: All criteria at 1.0 → total = 1.0
- **Test**: All criteria at 0.0 → total = 0.0
- **Test**: Mixed scores → correct weighted calculation
  - has_actionable_output=1.0 * 0.3 + structural_integrity=0.5 * 0.25 + requirement_coverage=0.5 * 0.25 + test_validation=0.5 * 0.2 = 0.65
- **File**: `test_eval_rubric_enhanced.py::TestScoreOutput`

#### Test 1.5: gate_check — Threshold Enforcement
- **Test**: Score 0.7 → pass
- **Test**: Score 0.6999 → fail
- **Test**: Score 0.0 → fail
- **Test**: Score 1.0 → pass
- **File**: `test_eval_rubric_enhanced.py::TestGateCheck`

### Category 2: Gold Standard Suite Tests

#### Test 2.1: CRUD Operations
- **Test**: Add case → get case → verify fields match
- **Test**: Add case → remove case → get case → None
- **Test**: Get all cases after adding 3 → returns 3
- **Test**: Remove non-existent case → returns False
- **File**: `test_test_suite.py::TestGoldStandardSuite`

#### Test 2.2: Persistence
- **Test**: Add case → create new suite instance (same path) → case exists
- **Test**: Default criteria thresholds are set correctly
- **File**: `test_test_suite.py::TestGoldStandardPersistence`

### Category 3: Workflow Tests

#### Test 3.1: Eval Gate Before Integration
- **Test**: Generate code that scores < 0.7 → integration NOT performed
  - Verify: main.ts not modified, state["integrated"] = False
- **Test**: Generate code that scores >= 0.7 → integration performed
  - Verify: main.ts modified, state["integrated"] = True
- **Test**: Eval failure → failed_criteria populated
- **File**: `test_workflow_unit.py` (update existing tests)

#### Test 3.2: Regression Check in Workflow
- **Test**: First run (no baseline) → regression_check.has_baseline = False
- **Test**: Second run with same quality → regression_check.regressed = False
- **Test**: Second run with degraded quality → regression_check.regressed = True
- **File**: `test_workflow_unit.py` (add new tests)

#### Test 3.3: No Redundant Eval in test Node
- **Test**: _node_test runs jest but does NOT run score_output
- **Verify**: RubricStore has exactly 1 entry per workflow run (not 2)
- **File**: `test_workflow_unit.py` (add new test)

### Category 4: Production Monitor Tests

#### Test 4.1: Structured Output
- **Test**: run_production_check() returns dict with keys: status, report, alert, timestamp
- **Test**: Healthy system → status = "healthy", alert = None
- **Test**: Degrading system → status = "degrading", alert is not None
- **File**: `test_production_monitor_enhanced.py::TestRunProductionCheck`

#### Test 4.2: Degradation Detection
- **Test**: 10+ entries, recent avg 15% below historical → degrading = True
- **Test**: 10+ entries, recent avg 5% below historical → degrading = False
- **Test**: < 2 entries → degrading = False (insufficient data)
- **File**: `test_production_monitor_enhanced.py::TestDegradationDetection`

#### Test 4.3: Quality Report
- **Test**: Report contains all required keys: total_runs, pass_rate, avg_score, per_criterion_avg, trend, criterion_detail, generated_at
- **Test**: Trend is one of: "stable", "degrading", "improving", "insufficient_data"
- **File**: `test_production_monitor_enhanced.py::TestQualityReport`

### Category 5: Feedback Loop Tests

#### Test 5.1: record_feedback
- **Test**: Valid feedback → close_the_loop called, entry flagged
- **Test**: Empty feedback → ignored, no error
- **Test**: Non-matching issue_url → logged, no crash
- **File**: `test_agentics_app.py` (new file)

#### Test 5.2: close_the_loop
- **Test**: Flagged entry written to RubricStore with flagged=True
- **Test**: flagged_at timestamp is set
- **File**: `test_production_monitor_enhanced.py::TestCloseTheLoop`

### Category 6: Integration Tests

#### Test 6.1: Full Workflow with Eval Gate
- **Setup**: Mock LLM to return code that scores above/below threshold
- **Verify**: Integration only happens when eval passes
- **File**: `test_workflow_integration.py` (new file)

#### Test 6.2: End-to-End Eval Loop
- **Setup**: Run full workflow with mock LLM
- **Verify**: score_output → gate_check → (pass → integrate | fail → retry)
- **Verify**: RubricStore has exactly 1 entry per run
- **File**: `test_workflow_integration.py` (new file)

## Test Coverage Requirements

| Module | Min Coverage | Key Functions |
|--------|-------------|---------------|
| eval_rubric.py | 95% | score_output, gate_check, record_failure, RegressionTracker |
| workflow.py | 90% | _node_generate_code_tests (eval gate path) |
| agentics.py | 85% | process_issue, run_regression_suite, record_feedback |
| production_monitor.py | 90% | run_production_check, check_degradation, get_quality_report |
| test_suite.py | 95% | All CRUD operations |
| state.py | 100% | All fields documented |

## Regression Gate (Pre-ship Requirement)

Before any code ships:
1. All 104 existing tests must pass
2. All new tests must pass
3. `make lint-python` must pass
4. No new mypy errors
5. Coverage must meet minimums above

## Test Execution Order

1. `make test-agents-unit-mock` — Fast, no Ollama (run first)
2. `make lint-python` — Lint check
3. `make test-agents-unit` — With Ollama (run after mock tests pass)
4. `make test-agents-integration` — Full integration (run last)
