# Architecture Documentation — Fix the Slop Refactor

## Overview

This document describes the architecture of the refactored agentics system, how each module implements the `fix_the_slop.md` quality principles, and how the pieces work together to form a complete eval loop.

## The Eval Loop (Core Concept from fix_the_slop.md)

```
┌─────────────────────────────────────────────────────────────────┐
│                     EVAL LOOP                                    │
│                                                                  │
│  Generate Output → Score It → Gate Check → Ship or Retry        │
│       ↑                                          │               │
│       └──────────── Feedback Loop ←──────────────┘               │
│                                                                  │
│  Three evaluation points:                                        │
│  1. BEFORE shipping (syntax, compilation, test quality, tests pass)│
│  2. AT RUNTIME (gate_check scores every output against threshold)│
│  3. IN PRODUCTION (continuous monitoring via cron)               │
└─────────────────────────────────────────────────────────────────┘
```

## Module Architecture

```
agents/agentics/src/
├── __init__.py          → Package exports
├── agentics.py          → AgenticsApp (entry point) [255+ lines]
├── circuit_breaker.py   → Circuit breaker + health monitor [458 lines]
├── config.py            → Configuration [207 lines]
├── eval_rubric.py       → Quality scoring + RegressionTracker + RubricStore [~470 lines]
├── exceptions.py        → Custom exceptions [83 lines]
├── mcp_client.py        → MCP client [154 lines]
├── monitoring.py        → Structured logging [~200 lines]
├── production_monitor.py→ Production monitoring + feedback loop [226 lines]
├── services.py          → Service management [386 lines]
├── state.py             → State TypedDict [~60 lines]
├── test_suite.py        → GoldStandardSuite [66 lines]
├── utils.py             → Utility functions [340 lines]
├── workflow.py          → LangGraph workflow [~950 lines]
```

**Total: 13 source files (down from 49, -73%)**

## Module Responsibilities

### 1. `eval_rubric.py` — The Quality Engine

**Purpose**: Score every LLM output against a quality benchmark before it ships.

**Components**:

| Component | Role | fix_the_slop.md Principle |
|-----------|------|--------------------------|
| `QualityRubric` | 7-criteria scorer | "Metrics: how you turn an output into a score, ideally 0 to 1" |
| `score_output()` | Weighted total + hard gates | "A quality benchmark has three parts: test cases, metrics, threshold" |
| `gate_check()` | Threshold enforcement (≥0.7) | "The threshold is the line you hold. 0.7 is a reasonable place to start" |
| `record_failure()` | Actionable failure context | "Fix what's failing" |
| `RegressionTracker` | Baseline comparison | "Regression testing: confirm a change didn't get worse" |
| `RubricStore` | Persistent JSONL store | "Score a sample of real executions continuously" |
| `_check_code_test_consistency()` | Import/export matching | Prevents test imports that don't match code exports |

**Quality Rubric Weights (7 criteria)**:
```python
WEIGHTS = {
    "has_actionable_output":  0.15,  # Is there any code at all?
    "compiles_successfully":  0.25,  # Does tsc --noEmit pass?
    "tests_pass":             0.20,  # Do the generated tests pass (jest returncode 0)?
    "test_quality":           0.20,  # Do tests actually check the right things?
    "structural_integrity":   0.10,  # Balanced braces/parens, valid syntax
    "requirement_coverage":   0.05,  # Does code address ticket requirements?
    "test_validation":        0.05,  # Heuristic test quality (assert count)
}
```

**Hard Gates (automatic fail regardless of other scores)**:
1. **Test consistency**: If test imports don't match code exports → total = 0, blocked
2. **Tests pass**: If `npx jest` returns non-zero → total = 0, blocked

**Note**: `compiles_successfully` (tsc --noEmit) is **NOT** a hard gate. It contributes 0.25 to the weighted score but won't block on its own.

**Threshold**: 0.7 (configurable via `EVAL_THRESHOLD` env var)

**Structural Integrity Gate Approach**:
- Balanced braces → max score = 0.4 if failed (not a hard gate)
- Balanced parens → max score = 0.4 if failed (not a hard gate)
- No broken clusters → 0.1 weight
- Line syntax validity → 0.9 weight
- Lines >200 chars are penalized
- **Const reassignment detection**: Catches common LLM error like `const x = 5; x = 10;`

**test_quality Check**: Validates that generated LLM tests are comprehensive:
- Tests actually call the generated function (not just `typeof` checks)
- Tests check return type is string
- Tests check output format/length (not just "is a string")
- Tests check uniqueness (multiple calls, different results)
- Tests have ≥3 `it()` blocks

### 2. `test_suite.py` — Gold Standard Management

**Purpose**: Manage gold standard test cases for regression testing.

**fix_the_slop.md Principle**: "Pull 20 to 50 of your best pieces, the bangers — this is what 'good' looks like."

**GoldStandardSuite**:
- `add_case(input, expected_output, criteria_thresholds)` → case_id
- `get_case(case_id)` → case dict
- `get_all_cases()` → list of all cases
- `remove_case(case_id)` → bool
- JSON persistence (versioned)
- Per-case criteria thresholds

### 3. `production_monitor.py` — Continuous Quality Monitoring

**Purpose**: Monitor quality in production, detect degradation, close the feedback loop.

**Components**:

| Component | Role | fix_the_slop.md Principle |
|-----------|------|--------------------------|
| `ProductionMonitor` | Aggregate stats + trend | "Score a sample of real executions continuously" |
| `ThresholdAlerter` | Alert on low scores | "The moment quality becomes a number, slop stops being a feeling" |
| `run_production_check()` | Cron-compatible check | "Watch production on a cron and close the loop" |
| `close_the_loop()` | Feedback → test case | "When you flag a bad output, it becomes a new test case" |

**Degradation Detection**: Recent window avg >10% below historical avg → degrading

**Quality Report Structure**:
```python
{
    "total_runs": int,
    "pass_rate": float,
    "avg_score": float,
    "per_criterion_avg": {criterion: float},
    "trend": "stable" | "degrading" | "improving" | "insufficient_data",
    "criterion_detail": {criterion: {recent_avg, recent_min, recent_max}},
    "generated_at": "ISO timestamp"
}
```

### 4. `state.py` — Workflow State

**Purpose**: Single TypedDict for entire workflow state (fix_the_slop.md: "Single State TypedDict throughout").

**Eval loop fields**:
- `regression_check`: dict from RegressionTracker.check_regression()
- `integrated`: bool (whether code was integrated after passing gate)
- `integration_blocked_reason`: str (why integration was blocked)
- `tests_passed`: bool (whether generated tests actually passed)
- `eval_failure_context`: str (fed back to LLM on retry)
- `recovery_attempt`: int (number of eval retries)

### 5. `workflow.py` — LangGraph Workflow

**8 nodes**: fetch_issue → clarify_ticket → plan_implementation → extract_code → generate_code_tests → test → output

**Conditional routing**: generate_code_tests → (eval_passed? → test) or (recovery_attempt < 3? → retry generate_code_tests) or (max retries → output with success=False)

**Eval gate in generate_code_tests node**:
1. LLM generates code + tests (up to 3 attempts each)
2. **Syntax check** before tests: `_is_valid_ts_syntax()` catches const reassignment, unbalanced braces/parens
3. Run generated tests via `npx jest`
4. **Compilation check**: `compiles_successfully` runs `tsc --noEmit`
5. **Test quality check**: `test_quality` validates tests are comprehensive
6. **Code-test consistency**: `_check_code_test_consistency` verifies imports match exports
7. **Score**: weighted total across 7 criteria
8. If pass → integrate into `main.ts` (import + addCommand), write generated tests to separate file, append integration tests to `main.test.ts`
9. If fail → record failure, feed context back to LLM, retry (up to 3 times)

**Integration process (only if ALL gates pass)**:
1. Write generated code to `src/generated/<slug>.ts`
2. Add import line to `main.ts` (after existing imports)
3. Add `addCommand` block to `main.ts` (inside `onload()` method)
4. Write generated tests to `src/__tests__/generated/<slug>.test.ts` (separate file)
5. Append integration tests to `src/__tests__/main.test.ts` (verifies command registration, editorCallback, import statement)

**Key design decisions**:
- Generated tests are SEPARATE from `main.test.ts` (not appended)
- Integration tests ARE appended to `main.test.ts` (verifies the integration worked)
- After 3 failed retries, workflow routes to `output` (not `test`) — prevents running tests on broken code
- `output` node sets `success=False` when `integrated=False`

### 6. `agentics.py` — Application Entry Point

**AgenticsApp**:
- `process_issue(url)`: Full workflow + eval scoring
- `get_quality_report()`: Production quality report
- `record_feedback(url, feedback)`: Close the feedback loop
- `run_regression_suite()`: Run gold standard cases through workflow

## Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        WORKFLOW                                   │
│                                                                   │
│  1. fetch_issue        → ticket_content                          │
│  2. clarify_ticket     → refined_ticket                         │
│  3. plan_implementation→ refined_ticket (enriched)               │
│  4. extract_code       → relevant_code_files, relevant_test_files│
│  5. generate_code_tests→ generated_code, generated_tests         │
│     ├─ _is_valid_ts_syntax() → fast reject (const reassign, etc) │
│     ├─ npx jest on generated tests → tests_passed               │
│     ├─ compiles_successfully() → tsc --noEmit                    │
│     ├─ test_quality() → validates test comprehensiveness        │
│     ├─ _check_code_test_consistency() → imports match exports   │
│     ├─ score_output() → 7-criteria weighted score + 2 hard gates│
│     ├─ gate_check() → pass/fail against 0.7 threshold            │
│     ├─ If pass → integrate main.ts + main.test.ts + baseline     │
│     └─ If fail → record_failure() + retry (max 3) or stop       │
│  6. test (post-integration) → jest on ALL tests (optional)       │
│  7. output → success=integrated, result dict                     │
│                                                                   │
│  ROUTING (conditional edge after generate_code_tests):           │
│  ├─ eval_passed=True → test                                      │
│  ├─ eval_passed=False, recovery_attempt<3 → generate_code_tests  │
│  └─ eval_passed=False, recovery_attempt>=3 → output (blocked)   │
│                                                                   │
│  POST-WORKFLOW:                                                   │
│  8. RubricStore.record(eval_result)                              │
│  9. RegressionTracker.save_if_improved()                         │
│ 10. ProductionMonitor (cron) → degradation alerts                │
│ 11. User feedback → close_the_loop() → RubricStore               │
└──────────────────────────────────────────────────────────────────┘
```

## The 2 Hard Gates (in execution order)

| # | Gate | Check | Auto-fail? |
|---|------|-------|------------|
| 1 | **Code-test consistency** | Test imports match code exports | Yes |
| 2 | **Tests pass** | `tests_pass()` returns 0.0 (no tests generated) | Yes |

**Not hard gates** (contribute to weighted score but don't block on their own):
| # | Gate | Check | Auto-fail? |
|---|------|-------|------------|
| 3 | **Syntax** | `_is_valid_ts_syntax()` — balanced braces/parens, no const reassignment | No (structural_integrity) |
| 4 | **Compilation** | `tsc --noEmit` on generated code returns 0 | No (compiles_successfully) |
| 5 | **Score threshold** | Weighted total ≥ 0.7 across 7 criteria | No (partial credit) |

Only gates 1-2 are hard gates: if either fails, the total score is immediately 0 regardless of other criteria.

## fix_the_slop.md Compliance Matrix

| Principle | Implementation | File |
|-----------|---------------|------|
| "Slop is a systems problem" | Eval loop with 2 hard gates before shipping | `eval_rubric.py` |
| "Eval = generate → score → catch → fix → re-score" | 3-attempt retry loop with eval scoring + LLM feedback | `workflow.py` |
| "Threshold = 0.7" | `gate_check()` enforces ≥0.7 with hard gates | `eval_rubric.py` |
| "Quality benchmark: 3 parts" | Test cases (GoldStandardSuite) + metrics (7 criteria) + threshold (0.7) | `eval_rubric.py` + `test_suite.py` |
| "Regression testing" | RegressionTracker compares vs baseline, 10% threshold | `eval_rubric.py` |
| "Production monitoring" | ProductionMonitor + run_production_check() | `production_monitor.py` |
| "Feedback loop closes" | close_the_loop() writes flagged → RubricStore | `production_monitor.py` |
| "Quality floor rises" | save_if_improved() only saves better scores | `eval_rubric.py` |
| "No silent failures" | Structured logging on every error path | `monitoring.py` |
| "Score is a number, not a feeling" | All scores 0-1, weighted total, threshold gate | `eval_rubric.py` |
| "Test YOUR OWN output" | test_quality() validates LLM-generated tests are comprehensive | `eval_rubric.py` |

## Configuration

| Environment Variable | Default | Purpose |
|---------------------|---------|---------|
| `EVAL_THRESHOLD` | 0.7 | Quality gate threshold |
| `EVAL_STORE_PATH` | /tmp/eval_results.jsonl | RubricStore JSONL path |

## Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| eval_rubric.py | ~50 | All 7 criteria, hard gates, consistency check, test_quality |
| test_suite.py | 14 | GoldStandardSuite CRUD, persistence, defaults |
| production_monitor_enhanced.py | 10 | run_production_check, degradation, ThresholdAlerter, close_the_loop |
| test_regression.py | ~20 | RegressionTracker save/load, regression detection, save_if_improved |
| test_state_unit.py | 4 | State TypedDict fields |
| test_config_unit.py | 18 | Configuration validation |
| test_exceptions_unit.py | 20 | Exception hierarchy |
| test_workflow_unit.py | ~70+ | All nodes, routing, eval gate, retry, regression, output |
| test_workflow_edge_cases.py | ~17 | Edge cases, routing |
| test_eval_gate_integration.py | ~15 | Gate pass/fail/integration behavior |
| **Total all tests** | **281+** | All pass |

## Relationship to Action Plans

| Action Plan | Implementation |
|-------------|---------------|
| `product-owner-plan.md` | P0: Eval loop complete ✓, P0: Regression testing ✓, P0: Production monitoring ✓, P1: Feedback loop ✓, P1: Quality dashboard ✓, P2: Gold standard ✓ |
| `architect-plan.md` | Eval gate before integration ✓, RegressionTracker ✓, GoldStandardSuite ✓, ProductionMonitor structured output ✓ |
| `developer-plan.md` | TASK-01 through TASK-07 all implemented ✓ |
| `tester-plan.md` | All 6 test categories covered ✓, 281+ tests pass ✓ |
