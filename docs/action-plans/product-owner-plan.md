# Product Owner Action Plan

## Vision

Transform the agentics code from an unmeasured AI output generator into a quality-gated system that catches slop before it ships. Every output must be scored, gated, and the floor must rise over time.

## Problem Statement (from fix_the_slop.md)

The current system generates code and tests but has no quality verification layer. The LLM produces output → it goes straight to integration → if tests fail, it retries blindly. There is no rubric, no scoring, no threshold gate, and no production monitoring. This is exactly "shipping every flip of the coin."

## Product Requirements (P0 = Must Have)

### P0 — Eval Loop Must Be Complete
- **Criteria**: `eval_rubric.py` scores every output on 4 criteria with weighted total
- **Acceptance**: Score < 0.7 blocks shipping, score >= 0.7 passes. No exceptions.
- **Metric**: `gate_check()` returns (False, reason) for anything below threshold
- **Current Gap**: The eval loop runs AFTER integration (too late). It should gate BEFORE integration.

### P0 — Regression Testing on Every Change
- **Criteria**: Any prompt/model/pipeline change triggers the full eval suite against saved test cases
- **Acceptance**: Score delta is computed; regression blocks deploy
- **Current Gap**: No regression testing exists. The code has a self-correction loop (3 attempts) but no saved baseline to compare against.

### P0 — Production Monitoring
- **Criteria**: `production_monitor.py` samples real executions continuously
- **Acceptance**: Degradation >10% triggers alert. Score line stays flat or climbs.
- **Current Gap**: `ProductionMonitor` exists but is never wired into a cron/scheduled check.

### P1 — Feedback Loop Closes
- **Criteria**: User-throttled/bad output becomes a new test case in the suite
- **Acceptance**: `close_the_loop()` writes flagged failures back to RubricStore with `flagged: true`
- **Current Gap**: `close_the_loop()` exists but is never called from any user-facing workflow.

### P1 — Quality Dashboard
- **Criteria**: `get_quality_report()` returns comprehensive stats including trend
- **Acceptance**: Report shows total_runs, pass_rate, avg_score, per_criterion_avg, trend direction
- **Current Gap**: Report function exists but has no consumer. No dashboard or cron reads it.

### P2 — Gold Standard Test Cases
- **Criteria**: 20-50 gold standard inputs with expected outputs stored as ground truth
- **Acceptance**: Test cases are versioned, queryable, and used in regression testing
- **Current Gap**: No gold standard exists. The system generates tests but has no reference "good" output.

## Quality Standards (Non-Negotiable)

1. **Threshold = 0.7** — Never ship below this. Period.
2. **All 4 criteria must be scored** — has_actionable_output, structural_integrity, requirement_coverage, test_validation
3. **Scores must be logged** — Every eval run writes to RubricStore (JSONL)
4. **Failures must be actionable** — `record_failure()` returns what_was_wrong + what_to_fix
5. **No silent failures** — Every error path logs with structured logging
6. **Test coverage must hold** — Existing 104 tests must pass after every change

## Acceptance Criteria for This Refactor

- [ ] Eval loop gates BEFORE code integration (not after)
- [ ] Regression testing compares against baseline scores
- [ ] Production monitoring runs on a schedule (cron)
- [ ] Feedback loop writes flagged failures back to store
- [ ] All existing 104 tests pass
- [ ] New tests cover the eval loop, gating, and production monitoring
- [ ] No code changes to `src/` (Obsidian plugin) — only `agents/agentics/`
- [ ] All changes scoped to `/home/asimov/repository/git/obsidian-timestamp-utility`

## Out of Scope

- Changes to the Obsidian plugin TypeScript code (`src/`)
- Changes to the Dagger pipeline (`dagger-pipeline/`)
- Changes to the Makefile
- Model upgrades or prompt changes (input-side fixes)
