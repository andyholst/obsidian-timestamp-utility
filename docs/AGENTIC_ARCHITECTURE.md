# Agentic Architecture (`agents/agentics/`)

> Canonical architecture reference for the Python agentic pipeline that turns an
> OpenSpec change (or a GitHub issue) into TypeScript + tests for the Obsidian
> plugin. This document is the single entry point for "how the agentic code is
> shaped"; the older design docs live alongside it in `docs/` and are linked
> where relevant.

## 1. Purpose

The agentic pipeline reads a change request — either a **local OpenSpec change**
(`openspec/changes/<name>/`) or a **live GitHub issue** — and produces, verifies,
and integrates TypeScript code + tests into `src/main.ts` / `src/__tests__/main.test.ts`.
It is driven end-to-end through the Makefile (`make run-agentics`, `make loop-harness`)
and executes only under docker compose (rootless nerdctl). No Dagger, no MCP.

It is the **generator** half of this repo's two disciplines (see
`docs/openspec-engineering-loop-harness.md`):
- *Harness engineering* = the deterministic floor that constrains LLM output into a known-good,
  checkable shape (the `CodeIntegratorAgent` merge, never the LLM, is the sole writer of `main.ts`).
- *Loop engineering* = the closed feedback loop that re-runs generation until an objective gate
  passes (`make build-app` + `make test-app` + a walk of every spec requirement).

## 2. Entry points

| Module | Role |
|--------|------|
| `src/agentics.py` | Application entry point. Initializes config/services/workflows, exposes `check_services()`, and wires every agent. |
| `src/composable_workflows.py` | Builds the three-phase LangGraph `StateGraph` from `AgentComposer` (`build_issue_processing`, `build_code_generation`, `build_integration_testing`). |
| `src/agent_composer.py` | `AgentComposer` + `WorkflowConfig`: registers agents/tools and constructs composable LCEL runnables. |
| `src/openspec_loader.py` | Reads a local OpenSpec change (`proposal.md` + `tasks.md` + `specs/**`) and synthesizes a GitHub-issue-shaped `ticket_content` so downstream agents are unchanged. Also `find_change_dir`, `create_change_from_issue` (B15 seed-then-generate), `assert_no_open_tasks` (B16). |
| `src/workflows.py` / `src/services.py` / `src/config.py` | Workflow/service/config singletons used across agents. |

## 3. Module / agent map

The pipeline agents each consume and extend `state["ticket_content"]` /
`state["url"]`. They are registered as runnables via `AgentComposer`.

### Issue processing phase
- `fetch_issue_agent.py` — fetches a live GitHub issue once (`state["url"]`); for local changes the `openspec_loader` seeds the content instead.
- `ticket_clarity_agent.py` — scores/improves ticket clarity.
- `implementation_planner_agent.py` — plans the implementation steps.
- `dependency_analyzer_agent.py` / `dependency_installer_agent.py` — analyze and install dependencies.

### Code generation phase (collaborative)
- `code_generator_agent.py` — proposes raw candidate TypeScript/test text (the LLM **never** holds the pen for the final file).
- `collaborative_generator.py` — `CollaborativeGenerator` orchestrates code + test generation together.
- `code_extractor_agent.py` — extracts code blocks from LLM output.
- `test_generator_agent.py` (`GeneratorAgent`) — generates the jest test bodies.
- `process_llm_agent.py` — generic LLM-call wrapper.
- `tool_integrated_agent.py` / `tool_executor.py` / `tools.py` — LangChain tools (file read/list, npm search/install/list) used by agents.

### Integration & testing phase (the deterministic floor)
- `code_integrator_agent.py` — **the sole writer of `src/main.ts`**. Merges the spec contract (parsed from `tasks.md` / `spec.md` markers) into the existing file deterministically (B7/B10/B11). `integrate_test_contract` / `_expected_contract_for_change` read the contract and inject it; no TS bodies are hard-coded in Python (B10).
- `post_test_runner_agent.py` — runs jest/build and drives the self-correct loop (`MAX_SELF_CORRECT_ATTEMPTS`).
- `pre_test_runner_agent.py` — pre-flight checks before test execution.
- `code_reviewer_agent.py` — reviews the merged code.
- `error_recovery_agent.py` — `TestRecoveryNeeded` handling + fallback.
- `output_result_agent.py` — emits the final result/state.
- `feedback_agent.py` — routes reviewer/validator feedback back into the loop.
- `hitl_node.py` — `HITLNode`: opt-in, pass-through in automation, prompts a human only when ALL hold (score < 80, not CI, `HITL_ENABLED=1`, `INTERACTIVE_HITL=1`, `isatty()`) (B21).

### Cross-cutting support
- `base_agent.py` — base agent class. `clients.py` — LLM/Ollama clients.
- `code_validator.py` / `llm_validator.py` — validation frameworks (see `docs/architecture/LLM_CODE_VALIDATION.md`).
- `circuit_breaker.py` — retry/breaker; `monitoring.py` — structured logging; `performance.py` — batch processing.
- `state.py` (`CodeGenerationState`, frozen dataclass) / `state_adapters.py` — immutable state + legacy adapters.
- `models.py`, `exceptions.py`, `prompts.py`, `utils.py` — shared models, errors, prompt templates, helpers.

## 4. The three-phase workflow

`composable_workflows.py` assembles a LangGraph `StateGraph`:

1. **ISSUE PROCESSING** — fetch/clarify/plan/analyze dependencies.
2. **CODE GENERATION (COLLABORATIVE)** — `code_generation` proposes candidate text; it is then
   routed to `code_integrator` (the deterministic floor) which merges the spec contract into
   `src/main.ts`. This step runs in **every** mode including fast mode (B7.1) — fast mode only
   skips the npm-test loop, never the integrator.
3. **INTEGRATION & TESTING** — `post_test_runner` → `error_recovery` → `code_integrator` re-merge
   → `code_reviewer` → `output_result`. On failure the loop self-corrects (fix the SPEC, restore,
   re-run — never hand-edit generated TS, B11).

The graph checkpoints via LangGraph `MemorySaver` (in-memory for local dev). HITL is a
pass-through node in the loop (B21).

## 5. The deterministic floor (why generated TS is reliable)

- **Single source of truth**: the authoritative TS/test bodies live ONLY in the change's
  `tasks.md` / `spec.md` fenced ```ts blocks, split by `=== CONTRACT_* ===` markers. Python only
  parses those markers and merges — it never contains TS body literals (B10; verified by
  `grep -nE "addCommand\(|extends obsidian\.Modal|describe\('" agents/agentics/src/*.py` returning
  only comments/idempotency guards).
- **LLM never holds the pen**: `CodeIntegratorAgent` is the sole writer of `src/main.ts`; the LLM
  only proposes raw candidate text (B7/B11).
- **Idempotent, checkable merge**: the integrator strips any non-contract `addCommand` and any
  existing/LLM Modal of the same name from BOTH the existing file and the LLM output, then injects
  the authoritative contract command + appends the spec Modal/generator only if absent.
- **Omission guard**: `make run-agentics` compares generated file size vs the timestamped backup;
  a shrink is a genuine omission only if the spec's contract command id is also missing (B5/B6).
- **Committed baseline restore**: the e2e harness restores `src/main.ts` to git HEAD after every
  run so it never leaves uncommitted generated TS behind (B5/B6).

## 6. Testing layout

- `tests/unit/` — hermetic tests; mock ONLY external boundaries (GitHub/Ollama/network/FS).
  Run on real agent units via `make test-agents-unit` (live Ollama) and `make test-agents-unit-mock`.
- `tests/integration/` — integration + e2e (`@pytest.mark.e2e`, `@pytest.mark.slow`,
  `@pytest.mark.integration`). Live-Ollama tests skip cleanly on `OLLAMA_HOST` absence; public
  GitHub reads run token-less. The standing e2e gates are `test_ticket20_*`, `test_ticket22_*`,
  `test_greetings_*` (see `openspec/specs/task-driven-ts-generation-e2e`).
- `tests/fixtures/` — shared mocks (circuit breaker, GitHub/LLM responses, scenarios).
- `fix_integration_tests.py` / `scripts/test_suite_validation.py` — suite hygiene helpers.

See also (under `docs/architecture/`): `docs/architecture/LLM_CODE_VALIDATION.md` (validation
framework), `docs/architecture/ARCHITECTURE_DEPENDENCY_MANAGEMENT.md` (dependency resolution),
`docs/architecture/TEST_SUITE_README.md` (test suite guide),
`docs/architecture/INTEGRATION_TEST_PLAN.md` (integration coverage plan).

## 7. Execution & boundaries

- **Docker compose only**: `containers/*` + `docker-compose-files/*`; rootless nerdctl. The repo is
  mounted at `/project`; the agentic code runs from `/app`. Resolve the project root by probing for a
  directory containing `openspec/changes` (never a fixed relative depth) (B19).
- **Permissions floor (B9)**: `make b9-perms` applies `chmod -R a+rX` (read) + `chmod -R a+rwX`
  (write targets) so the remapped container uid can read/write.
- **No git commit/push (B4/B14)**: the pipeline writes/merges TS + spec files only; committing is a
  deliberate, separate human action.

## 8. Relationship to the harness/loop engineering doc

This file describes **what the agentic code is and how it is structured**. The operational
"how the whole loop is run and verified" reference is `docs/openspec-engineering-loop-harness.md`
(and `AGENTS.md` + `hermes/skills/openspec-loop-harness.md`, kept in sync per B8). The durable
behaviours B1–B25 enforced by the loop are defined there and in `AGENTS.md`.
