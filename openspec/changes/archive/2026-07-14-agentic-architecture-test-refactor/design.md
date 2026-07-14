# Design — agentic-architecture-test-refactor

## Architecture (current, to be documented)
Entry: `prod.agentics` (`python -m prod.agentics <openspec:change>`) →
`composable_workflows` runs a graph:
`fetch_issue_agent` (local change via `openspec_loader.load_change`) →
`ticket_clarity_agent` → `implementation_planner_agent` →
`code_generator_agent` (or `collaborative_generator` / `tool_integrated_code_generator_agent`)
→ `test_generator_agent` → `code_integrator_agent` → `pre_test_runner_agent` →
`post_test_runner_agent` → `error_recovery_agent`. Supporting: `code_reviewer_agent`,
`code_validator`, `llm_validator`, `feedback_agent`, `hitl_node`, `state_adapters`,
`state`, `prompts`, `tools`, `clients`, `models`, `config`, `monitoring`,
`circuit_breaker`, `performance`, `services`, `workflows`, `mcp_client`, `api_validation_tools`.

## Assessment method
1. Build an **import graph** of `agents/agentics/src` from `prod.agentics` entry; mark each
   module reachable or orphan. Orphans → candidate dead-code removal (allowlist kept:
   `__init__`, `utils`, `exceptions`, `models`, `config`, `prompts`, `state`, `tools`,
   `clients`, `monitoring`).
2. For each live module on the TS-generation path, confirm ≥1 real unit test exists.
3. Identify dead tests (target deleted module / only assert on mocked-out dead logic / dup).

## Known weak point (must fix)
- `code_integrator_agent` currently **replaces** `main.ts` with generated content (observed:
  output 2115b vs 7635b backup → omission). Loop-readiness requires it to **merge** (append
  the new command/function, preserve existing). This is the top architecture fix.

## Refactor rules
- Remove only reference-checked dead modules; keep allowlisted utilities.
- Remove only dead tests; keep all live-module tests green.
- Do not drop coverage below baseline (measure with `pytest --cov` on unit).

## Verification
- Import-graph scan clean (no live import of deleted module).
- `make test-agents-real` (unit real-logic + integration real-call) passes.
- Unit coverage ≥ baseline.
