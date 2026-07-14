# Design — python-agentic-slim-refactor

## Goal
Reduce the complexity of the Python agentic generation pipeline so it **resembles the
harness / loop / OpenSpec engineering model** (one deterministic sole-writer floor, one bounded
self-correct loop, spec/contract wins) — while preserving behaviour, gated by the ticket20/22/gr
eetings e2e proof-of-concept.

## Final module classification (measured, not guessed — AST import-reachability + live-graph scan)

- **Reachable from entry `agentics`:** 42/45 modules. Only true import-orphans: `test_suite`
  (standalone validation tool, reached only by its own unit test) and `api_validation_tools`
  (unimported entirely).
- **Live graph nodes (what actually runs in `full_workflow` / `integration_testing`):**
  `code_integrator`, `dependency_installer`, `pre_test_runner`, `post_test_runner`,
  `error_recovery`, `hitl`, `code_reviewer`, `output_result`. (+ `code_extractor`,
  `collaborative_generator` via `code_generation_workflow`; `fetch_issue`/`ticket_clarity`/
  `implementation_planner`/`dependency_analyzer` via `issue_processing_workflow`.)
- **Generator stack is LIVE** (NOT dead): `code_extractor → collaborative_generator →
  CodeGeneratorAgent`. Do not delete these.
- **Test-reachable (keep intact):** `code_validator` (consumed by `code_reviewer` +
  `test_suite` + integration tests), `test_suite` (standalone tool). Removing/slimming them
  would break the integration suite — out of scope.

## Removed / consolidated (behaviour-preserving)

| Item | LOC | Why safe | Gate |
|------|-----|----------|------|
| `api_validation_tools.py` → `.quarantine/` | ~8.4 KB | Import-orphan, only a cosmetic prompt string referenced it | ticket20/22 e2e GREEN |
| Unregister `tool_integrated` agent (keep base file) | — | Registered but never in any `agent_names` list | ticket20/22 e2e GREEN |
| Remove dead `InitialStateAdapter` | −42 | Imported, instantiated 0× , no test refs | 34 unit tests green |
| Remove `TEST_ULTRA_FAST_MODE` inline TS-writing block (233 LOC) | ~250–300 | Bypassed `code_integrator` floor (B10/B11); duplicate self-correct loop | ticket20/22 e2e 2/2 GREEN |
| Dead helpers: `retry_with_backoff_async`, `get_code_validator`, `get_response_validator` | ~55 | Zero references in src/ + tests/ | code_validator unit 92/92; e2e 2/2 |
| Duplicate imports in `composable_workflows.py` | minor | Second `Runnable`/`import os` dupes | 29 unit tests green |
| `route_hitl` → module-level staticmethod; fast mode routes through `code_integrator` | — | Fixes B7.1: floor must run in fast mode | 15 unit + 3 e2e GREEN |

## Key fixes surfaced by the proof-of-concept

1. **Fast mode bypassed the sole-writer floor (B7.1, B10/B11).** `route_hitl` returned
   `output_result` under `TEST_FAST_MODE=1`, skipping `integration_testing` (the only sub-graph
   with `code_integrator`). The deterministic contract was never injected; raw LLM output landed
   in `main.ts`. Exposed by the **greetings** e2e (modal absent from the committed baseline).
   Fixed: fast mode now routes `code_generation → code_integrator → output_result`. Slow path
   unchanged.
2. **uuid-specific contract parser (B9.4).** `_expected_contract_for_change` matched command *name*
   with a uuid-only regex, so `name: 'Show Greetings'` was dropped → incomplete contract → floor
   bailed. Fixed: generic name parser (prefers `name:` inside the `CONTRACT_COMMAND` block).

## Verification

- `import src.agentics` OK.
- Hermetic unit: `test_composable_workflows_unit` 15/15, `test_pipeline_flow_alignment_unit`
  5/5, `test_code_validator_unit` 92/92, `test_integrator_merge_unit` + `test_code_integrator_
  agent_unit` 29/29, new `test_slim_refactor_invariants_unit` 6/6.
- **E2E proof-of-concept (3/3 GREEN):** `test_ticket20_e2e_integration` + `test_ticket22_e2e_
  integration` (GitHub-issue seed-then-generate) + `test_greetings_e2e_integration` (local change,
  the non-algorithmic proof). Greetings is the critical guard: its modal is absent from the
  baseline, so it proves the *floor* (not the baseline) injected the feature.
- `make run-agentics CHANGE=greetings-modal-agentic-generation` and `CHANGE=uuid-modal-agentic-
  generation` (docker-compose, Ollama) exercised; generated TS restored to git HEAD after (B5).

## Harness alignment achieved

- One writer: `CodeIntegratorAgent` (deterministic floor) — unconditional, all modes.
- One bounded self-correct loop: `error_recovery` node.
- Spec/contract wins: no hardcoded `generateUUIDv7`; contract TS lives only in the OpenSpec change
  (`=== CONTRACT_* ===` markers), parsed by `_expected_contract_for_change`.
- B8 sync: findings mirrored into `AGENTS.md` (B7.1, three-e2e gate) and
  `hermes/skills/openspec-loop-harness.md` (B7.1, fast-mode-floor + ultra-fast-legacy pitfalls).
