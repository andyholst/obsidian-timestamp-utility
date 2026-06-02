# AGENTS.md

## Core
- **Makefile + Dagger only**: Run `make help` first. `make setup-dev` for Dagger/engine. **Never** run npm/docker/ollama/Python directly. Trust Makefile/Dagger pipelines over README.md.
- Env: Set `GITHUB_TOKEN` (agents), `OLLAMA_MODEL=sorc/qwen3.5-claude-4.6-opus:9b`, `OLLAMA_CODE_MODEL=sorc/qwen3.5-claude-4.6-opus:9b`. **Never use bare `qwen3.5:9b` or `qwen3.5:4b`**.
- Structure: `src/` (Obsidian TS plugin), `agents/agentics/` (LangGraph agent workflow + tests), `dagger-pipeline/` (all build/test logic). Plugin edits independent of agents.
- Cleanup: `make clean`, `make clean-dagger-engine` or `make nuke-dagger` for Dagger issues. `make fix-perms` auto-runs after most targets.

## Plugin (src/)
- Entry: `src/main.ts` (6 commands: timestamp insert/rename variants, date-range modal, reminder-to-task processor).
- Build/test: `make test-app` (Rollup CJS to dist/main.js + Jest in src/__tests__/). No separate lint; strict TS.
- Install: Copy `dist/main.js` + `manifest.json` to `.obsidian/plugins/timestamp-utility/` (exact match to manifest.id; avoid desktop-only APIs).
- CI: Only `make test-app` on non-main. Bump version in both package.json + manifest.json.
- **Never edit dist/**. Use `make build-app` before manual testing.

## Agents (agents/agentics/)
- LangGraph-based workflow: 7 nodes — fetch → clarify → plan → extract → generate_code_tests (includes validate + integrate sub-steps) → test → output.
- Self-correction loop in generate_code_tests node: 7-criteria eval gate scoring with 3 retry attempts. `compiles_successfully` is NOT a hard gate (only code-test consistency and `tests_pass==0.0` are). Failed attempts feed `eval_failure_context` back to LLM.
- Single State TypedDict throughout — no adapter layers.
- E2E tests target real issues (#20, #22) with real Ollama + GitHub API.
- Unit tests: 104 tests covering nodes, helper functions, edge cases (empty inputs, LLM failures, GitHub failures, state preservation).

### Makefile Targets
- `make test-agents-unit-mock` — Mocked unit tests (fast, no Ollama).
- `make run-agentics ISSUE_URL=...` — Full workflow with real Ollama + GitHub.
- `make test-agents-integration` — Full integration tests (needs GITHUB_TOKEN, live Ollama).
- `make test-agents` — All agent tests.

### Key Source Files
- `src/workflow.py` — `AgenticsWorkflow` class: LangGraph `StateGraph` with 7 nodes, compile with `MemorySaver`.
- `src/agentics.py` — `AgenticsApp`: service init, workflow creation, `process_issue()` API.
- `src/state.py` — `State` TypedDict (single state type for entire workflow), includes `eval_failure_context`.
- `src/services.py` — `ServiceManager`: Ollama, GitHub, MCP clients.
- `src/config.py` — `AgenticsConfig`: Pydantic config, model names, timeouts.
- `src/eval_rubric.py` — `QualityRubric`: 7-criteria scoring, gate check, regression tracking.
- `src/circuit_breaker.py` — Circuit breaker + health monitor.
- `src/monitoring.py` — Structured logging.
- `src/production_monitor.py` — Production monitoring + feedback loop.
- `src/mcp_client.py` — MCP client.
- `src/test_suite.py` — `GoldStandardSuite`: gold standard test case management.
- `src/utils.py` — Utility functions.
- `src/exceptions.py` — Custom exceptions.

### Test Files
- `tests/unit/test_workflow_unit.py` — Node-by-node with mocked LLM/GitHub.
- `tests/unit/test_workflow_edge_cases.py` — Empty inputs, failures, state preservation, routing.
- `tests/unit/test_workflow_integration.py` — Workflow integration tests.
- `tests/unit/test_state_unit.py` — State TypedDict fields.
- `tests/unit/test_config_unit.py` — Config validation.
- `tests/unit/test_exceptions_unit.py` — Exception hierarchy.
- `tests/unit/test_eval_rubric_enhanced.py` — All 7 criteria, hard gates, consistency check, test_quality.
- `tests/unit/test_eval_gate_integration.py` — Gate pass/fail/integration behavior.
- `tests/unit/test_circuit_breaker.py` — Circuit breaker + health monitor.
- `tests/unit/test_services.py` — Service manager, Ollama/GitHub/MCP clients.
- `tests/unit/test_production_monitor_enhanced.py` — run_production_check, degradation, ThresholdAlerter.
- `tests/unit/test_test_suite.py` — GoldStandardSuite CRUD, persistence.
- `tests/unit/test_regression.py` — RegressionTracker save/load, regression detection.
- `tests/integration/test_ticket20_e2e_integration.py` — E2E with real Ollama + GitHub (issue #20).
- `tests/integration/test_ticket22_e2e_integration.py` — E2E with real Ollama + GitHub (issue #22).
- `tests/integration/test_test_suite_integration.py` — Test suite integration.

### Eval Gate
- 7-criteria weighted scoring via `QualityRubric.score_output()`.
- **Hard gates**: code-test consistency (imports match exports) and `tests_pass==0.0` (npx jest returns non-zero) → total = 0.
- `compiles_successfully` (tsc --noEmit) is **NOT** a hard gate — it contributes 0.25 to the weighted score but won't block on its own.
- Threshold: 0.7. Failed outputs retry up to 3 times with `eval_failure_context` fed back to LLM.

## Release
- `make release` after version bump (builds changelog + ZIP in release/).
- No pre-commit hooks. Avoid committing secrets.

## Gotchas
- Dagger engine state is fragile; use dedicated start/stop/clean targets.
- For Obsidian plugin work only, ignore agents/ entirely.
- `sorc/qwen3.5-claude-4.6-opus:9b` is the ONLY valid model name. No exceptions.
