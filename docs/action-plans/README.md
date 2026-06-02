# Fix the Slop — Action Plans

This directory contains role-specific action plans for refactoring the agentics Python code to follow the quality practices described in `fix_the_slop.md`.

## Key Principles from fix_the_slop.md

1. **Slop is a systems problem, not a prompt problem** — The eval loop is the missing layer
2. **Eval loop = generate → score → catch → fix → re-score → gate**
3. **Three evaluation points**: before shipping (regression), at runtime (guardrail), in production (continuous monitoring)
4. **Quality benchmark has three parts**: test cases, metrics (0-1), threshold (gate)
5. **The threshold is the line you hold** — 0.7 minimum, never let a 0.6 through
6. **Close the loop** — user feedback becomes new test cases, quality floor rises weekly
7. **Test YOUR OWN output** — Generated tests must be comprehensive, not trivial

## Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | This file — overview and index |
| `ARCHITECTURE.md` | Module architecture, responsibilities, data flow, compliance matrix |
| `ARCHITECTURE_FLOW.md` | **Complete step-by-step flow diagrams** — the 5 hard gates, 7 criteria, routing logic, integration process, anti-slop protection summary |
| `product-owner-plan.md` — Product vision, acceptance criteria, quality standards |
| `architect-plan.md` | System design, module architecture, integration points |
| `developer-plan.md` | Implementation tasks, code changes, file-by-file breakdown |
| `tester-plan.md` | Test strategies, regression gates, coverage requirements |
| `IMPLEMENTATION_SUMMARY.md` | What was actually changed and why |
| `FINAL_REPORT.md` | Final metrics, verification results |
| `SECURITY_PLAN.md` | Security analyst audit tasks |
| `PO_REVIEW.md` | Product owner approval |

## Quick Reference: The 2 Hard Gates (+ Weighted Quality Checks)

1. **Code-test consistency** — Test imports match code exports (HARD: total=0 on fail)
2. **Tests pass** — `tests_pass()` returns 0.0, meaning no test code was produced (HARD: total=0 on fail)

Weighted criteria (contribute to score, not hard gates):
3. **Syntax** — Balanced braces/parens, no const reassignment (via `structural_integrity` criterion)
4. **Compilation** — `tsc --noEmit` passes (via `compiles_successfully` criterion)
5. **Score threshold** — Weighted total ≥ 0.7 across 7 criteria (via `gate_check`)

Note: `compiles_successfully` is **NOT** a hard gate; it returns neutral 0.5 if tsc is unavailable.

## Quick Reference: 7 Quality Criteria

| Criterion | Weight | Checks |
|-----------|--------|--------|
| compiles_successfully | 0.25 | tsc --noEmit (weighted only, NOT a hard gate) |
| tests_pass | 0.20 | npx jest returncode (HARD GATE — total=0 if no tests generated) |
| test_quality | 0.20 | Tests are comprehensive |
| has_actionable_output | 0.15 | Non-empty code |
| structural_integrity | 0.10 | Balanced braces/parens |
| requirement_coverage | 0.05 | Addresses ticket |
| test_validation | 0.05 | Assert count |

## Key Metrics

- **Source files**: 49 → 13 (-73%)
- **Lines of code**: 16,747 → ~3,500 (-79%)
- **Unit tests**: 281+ passing, 0 failures
- **Build**: SUCCESS
- **Plugin tests**: All pass
