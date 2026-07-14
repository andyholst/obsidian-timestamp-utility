# python-agentic-slim-refactor — Work Log

**Date:** 2026-07-14
**OpenSpec Change:** `python-agentic-slim-refactor`
**Branch:** `setup-loop-harness-openspec`

## Summary
Analysis-driven refactor of the Python agentic generation pipeline to make it resemble the
harness / loop / OpenSpec engineering model (one deterministic sole-writer floor, one bounded
self-correct loop, spec/contract wins). Gated by the ticket20/22/greetings e2e proof-of-concept.

## Tasks Completed
- AST import-reachability + live-graph scan → classified modules (generators are LIVE; only
  `api_validation_tools` is a true import-orphan; `test_suite`/`code_validator` are test-reachable).
- Removed: `api_validation_tools.py` → `.quarantine/`, unregistered `tool_integrated` agent (kept
  base file), dead `InitialStateAdapter` (−42 LOC), dead helpers (`retry_with_backoff_async`,
  `get_code_validator`, `get_response_validator`, ~55 LOC), duplicate imports.
- Removed the 233-line `TEST_ULTRA_FAST_MODE` inline TS-writing block (bypassed the `code_integrator`
  sole-writer floor — a B10/B11 violation; duplicated the self-correct loop).
- **Fixed (§9.4):** uuid-specific contract-NAME parser → generic, so `name: 'Show Greetings'`
  parses and the deterministic floor injects the greetings feature.
- **Fixed (§10/B7.1):** `route_hitl` fast mode (set by conftest) used to skip `integration_testing`
  (the only sub-graph with `code_integrator`), so the spec contract was never injected in fast mode.
  Now fast mode routes `code_generation → code_integrator → output_result`; slow path unchanged.
  `route_hitl` promoted to a module-level staticmethod (testable).
- Added `tests/integration/test_greetings_e2e_integration.py` (the third e2e gate) + new hermetic
  `tests/unit/test_slim_refactor_invariants_unit.py` (fast-mode floor routing + generic parser).
- **B8 sync:** mirrored findings into `AGENTS.md` (B7.1, three-e2e gate) and
  `hermes/skills/openspec-loop-harness.md` (B7.1, fast-mode-floor + ultra-fast-legacy pitfalls).

## Verification Against Spec
| Requirement (harness/loop/OpenSpec) | Result |
|---|---|
| Deterministic sole-writer floor runs in ALL modes (B7/B7.1/B10/B11) | PASS — fast-mode route fixed; 3 e2e green |
| Spec/contract wins (no hardcoded TS bodies in Python, B10) | PASS — grep clean; contract TS only in OpenSpec change markers |
| One bounded self-correct loop (error_recovery) | PASS — present in `integration_testing` sub-graph |
| OpenSpec CLI seeds local change (B15) | PASS — ticket20/22 e2e seed-then-generate |
| Behaviour preserved (e2e proof-of-concept) | PASS — ticket20 + ticket22 + greetings 3/3 GREEN |
| `make run-agentics` (docker, Ollama) | PASS — greetings + uuid both complete, omission guard OK |
| `openspec validate` + `status` | PASS — 4/4 artifacts complete |

## Key Decisions
- Kept generators, `code_validator`, `test_suite` — they are LIVE or test-reachable; removing them
  would break the integration suite (out of scope).
- `TEST_ULTRA_FAST_MODE` kept as a legacy no-op in two sub-workflow agents (does not gate the TS
  writer anymore); documented rather than deleted to avoid disturbing LLM-prompt branching.
- Generated TS restored to git HEAD after each `make run-agentics` (B5); nothing committed/pushed
  (B14 — human step).

## Current Status
Change complete and verified. Ready for `openspec archive python-agentic-slim-refactor` (spec-only
merge) and a human-triggered commit/push of the slimmed Python + new tests + synced docs.

## Recommended Next Steps
- Optionally clean up the lingering `TEST_ULTRA_FAST_MODE` references in `collaborative_generator`
  / `implementation_planner_agent` (pure cosmetic now).
- Consider a follow-up change to consolidate the oversized live modules (`code_integrator_agent`,
  `code_generator_agent`) — deeper, higher-risk, not needed for this refactor's goal.
