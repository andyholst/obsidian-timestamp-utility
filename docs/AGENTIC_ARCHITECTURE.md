# Architecture — the whole system (`docs/AGENTIC_ARCHITECTURE.md`)

> Canonical, full-system architecture reference for this repository. This is the single
> entry point for "how the system is shaped": the **Obsidian plugin** (what runs), the
> **Python agentic pipeline** (how the plugin is generated), and the **OpenSpec loop /
> harness** (the discipline that binds generation to verification and archival). Older,
> narrower design docs live alongside it in `docs/architecture/` and are linked where
> relevant.

## 1. System overview (read this first)

This repository is **two-sided**, and a third coordinating discipline holds the two sides
together:

```
            ┌──────────────────────────────────────────────────────────┐
            │  OpenSpec loop / harness (docs/openspec-engineering-      │
            │  loop-harness.md) — generate → verify → archive           │
            └───────────────▲───────────────────────────┬──────────────┘
                            │ drives                    │ produces
                            │                           ▼
            ┌───────────────┴───────────────┐   ┌──────────────────────────┐
            │  Python agentic pipeline       │   │  Obsidian TypeScript      │
            │  (agents/agentics/)            │   │  plugin (src/main.ts …)   │
            │  LangChain + LangGraph         │   │  → rollup → dist/main.js  │
            │  reads openspec/changes/*      │   │  9 commands, the product  │
            │  writes src/main.ts (+tests)   │   │  a user installs          │
            └───────────────────────────────┘   └──────────────────────────┘
```

- **The plugin (runtime / product).** A TypeScript Obsidian plugin that registers nine
  commands for timestamps, file renaming, date ranges, UUID v7, Base64, and reminder
  conversion. Built with rollup into `dist/main.js` and shipped as a community plugin
  (`manifest.json`, current version **0.4.11**). This is what an end user installs and uses.
- **The agentic pipeline (generator).** A Python application (`agents/agentics/`) that reads
  an OpenSpec change (or a GitHub issue) and **deterministically generates** the plugin's
  TypeScript and jest tests. The LLM proposes candidate code; a deterministic merge floor
  (`CodeIntegratorAgent`) is the *sole* writer of `src/main.ts`. No Dagger, no MCP — runs
  only under docker compose (rootless nerdctl).
- **The OpenSpec loop / harness (discipline).** The operational wrapper that repeatedly
  runs the pipeline, the build (`make build-app`), and the tests (`make test-app`) until an
  objective gate passes (green build + green tests + every spec requirement walked), then
  archives the change's specs into `openspec/specs/`. Its durable behaviours B1–B25 are the
  authoritative source of truth and are documented in
  `docs/openspec-engineering-loop-harness.md` (and mirrored in `AGENTS.md`).

> The plugin you install is the *output* of the loop: the loop drives the pipeline, the
> pipeline writes the plugin. This document maps all three; the loop's operational detail
> lives in the harness reference linked above.

## 2. Plugin surface (the runtime product)

### 2.1 The nine commands

All commands are registered in `src/main.ts` (`this.addCommand({...})`) inside
`TimestampPlugin.onload()`. Their canonical `id`s (mirrored in `manifest.json`'s
`id: timestamp-utility`):

| `id` | Friendly name | Interaction |
|------|---------------|-------------|
| `insert-timestamp` | Insert Current Timestamp (YYYYMMDDHHMMSS) | editor callback — inserts `YYYYMMDDHHMMSS` at cursor |
| `rename-with-timestamp` | Rename with Timestamp Prefix | renames active file to `YYYYMMDDHHMMSS_<sanitized-basename>` |
| `rename-with-timestamp-title` | Rename with Timestamp Prefix + First Heading Title | `YYYYMMDDHHMMSS_<first-h1-title>` (or `untitled`) |
| `rename-filename-with-title` | Rename with First Heading Title | `<first-h1-title>.md` (or `untitled.md`) |
| `insert-date-range` | Insert Dates in Range (YYYY-MM-DD) | opens `DateRangeModal`; inserts one `YYYY-MM-DD` per line |
| `insert-uuid-v7` | Insert UUID v7 (timestamp-based) | editor callback — inserts a time-sortable UUID v7 at cursor |
| `encode-base64-message` | Encode Base64 Message | opens `Base64Modal(mode='encode')` |
| `decode-base64-message` | Decode Base64 Message | opens `Base64Modal(mode='decode')` |
| `process-tasks` | Convert Reminders to Date-Time-Blocked Tasks | opens `FolderSelectorModal`, converts `@YYYY-MM-DD HH:MM` reminders into daily time-blocked files |

### 2.2 Supporting modules (`src/*.ts`)

- `src/main.ts` — `TimestampPlugin` (extends `obsidian.Plugin`): command registration,
  timestamp generation, file-rename helpers, and the reminder→task conversion entry point.
- `src/folderSelectorModal.ts` — `FolderSelectorModal`: fuzzy source/output folder picker
  used by `process-tasks` to choose which folders to scan and write.
- `src/__tests__/main.test.ts` — the jest test suite for the plugin (generated/maintained
  by the agentic pipeline).
- `src/__mocks__/` — jest mocks for Obsidian APIs.

### 2.3 Build & distribution

- `rollup.config.js` bundles `src/main.ts` → `dist/main.js` (CommonJS, `external: ['obsidian']`,
  terser minified). `make build-app` runs it.
- `manifest.json`, `versions.json`, `styles.css` + `dist/` are what an Obsidian vault's
  `.obsidian/plugins/timestamp-utility/` directory consumes.
- `jest.config.cjs` + `make test-app` run the jest suite against the compiled plugin logic.

## 3. Agentic pipeline (the generator)

### 3.1 Purpose

The pipeline reads a change request — either a **local OpenSpec change**
(`openspec/changes/<name>/`) or a **live GitHub issue** — and produces, verifies, and
integrates TypeScript code + tests into `src/main.ts` / `src/__tests__/main.test.ts`. It is
driven end-to-end through the Makefile (`make run-agentics`, `make loop-harness`) and
executes only under docker compose (rootless nerdctl). No Dagger, no MCP.

It is the **generator** half of this repo's two disciplines (see the harness reference):
- *Harness engineering* = the deterministic floor that constrains LLM output into a
  known-good, checkable shape (the `CodeIntegratorAgent` merge, never the LLM, is the sole
  writer of `main.ts`).
- *Loop engineering* = the closed feedback loop that re-runs generation until an objective
  gate passes (`make build-app` + `make test-app` + a walk of every spec requirement).

### 3.2 Entry points

| Module | Role |
|--------|------|
| `agents/agentics/src/agentics.py` | Application entry point. Initializes config/services/workflows, exposes `check_services()`, and wires every agent. |
| `agents/agentics/src/composable_workflows.py` | Builds the three-phase LangGraph `StateGraph` from `AgentComposer` (`build_issue_processing`, `build_code_generation`, `build_integration_testing`). |
| `agents/agentics/src/agent_composer.py` | `AgentComposer` + `WorkflowConfig`: registers agents/tools and constructs composable LCEL runnables. |
| `agents/agentics/src/openspec_loader.py` | Reads a local OpenSpec change (`proposal.md` + `tasks.md` + `specs/**`) and synthesizes a GitHub-issue-shaped `ticket_content` so downstream agents are unchanged. Also `find_change_dir`, `create_change_from_issue` (B15 seed-then-generate), `assert_no_open_tasks` (B16). |
| `agents/agentics/src/workflows.py` / `services.py` / `config.py` | Workflow/service/config singletons used across agents. |

### 3.3 Module / agent map

The pipeline agents each consume and extend `state["ticket_content"]` / `state["url"]`. They
are registered as runnables via `AgentComposer`.

**Issue processing phase**
- `fetch_issue_agent.py` — fetches a live GitHub issue once (`state["url"]`); for local changes the `openspec_loader` seeds the content instead.
- `ticket_clarity_agent.py` — scores/improves ticket clarity.
- `implementation_planner_agent.py` — plans the implementation steps.
- `dependency_analyzer_agent.py` / `dependency_installer_agent.py` — analyze and install dependencies.

**Code generation phase (collaborative)**
- `code_generator_agent.py` — proposes raw candidate TypeScript/test text (the LLM **never** holds the pen for the final file).
- `collaborative_generator.py` — `CollaborativeGenerator` orchestrates code + test generation together.
- `code_extractor_agent.py` — extracts code blocks from LLM output.
- `test_generator_agent.py` (`GeneratorAgent`) — generates the jest test bodies.
- `process_llm_agent.py` — generic LLM-call wrapper.
- `tool_integrated_agent.py` / `tool_executor.py` / `tools.py` — LangChain tools (file read/list, npm search/install/list) used by agents.

**Integration & testing phase (the deterministic floor)**
- `code_integrator_agent.py` — **the sole writer of `src/main.ts`**. Merges the spec contract (parsed from `tasks.md` / `spec.md` markers) into the existing file deterministically (B7/B10/B11). `integrate_test_contract` / `_expected_contract_for_change` read the contract and inject it; no TS bodies are hard-coded in Python (B10).
- `post_test_runner_agent.py` — runs jest/build and drives the self-correct loop (`MAX_SELF_CORRECT_ATTEMPTS`).
- `pre_test_runner_agent.py` — pre-flight checks before test execution.
- `code_reviewer_agent.py` — reviews the merged code.
- `error_recovery_agent.py` — `TestRecoveryNeeded` handling + fallback.
- `output_result_agent.py` — emits the final result/state.
- `feedback_agent.py` — routes reviewer/validator feedback back into the loop.
- `hitl_node.py` — `HITLNode`: opt-in, pass-through in automation, prompts a human only when ALL hold (score < 80, not CI, `HITL_ENABLED=1`, `INTERACTIVE_HITL=1`, `isatty()`) (B21).

**Cross-cutting support**
- `base_agent.py` — base agent class. `clients.py` — LLM/llama clients.
- `code_validator.py` / `llm_validator.py` — validation frameworks (see `docs/architecture/LLM_CODE_VALIDATION.md`).
- `circuit_breaker.py` — retry/breaker; `monitoring.py` — structured logging; `performance.py` — batch processing.
- `state.py` (`CodeGenerationState`, frozen dataclass) / `state_adapters.py` — immutable state + legacy adapters.
- `models.py`, `exceptions.py`, `prompts.py`, `utils.py` — shared models, errors, prompt templates, helpers.

### 3.4 The three-phase workflow

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

### 3.5 The deterministic floor (why generated TS is reliable)

- **Single source of truth**: the authoritative TS/test bodies live ONLY in the change's
  `tasks.md` / `spec.md` fenced `ts` blocks, split by `=== CONTRACT_* ===` markers. Python only
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

### 3.6 Testing layout

- `agents/agentics/tests/unit/` — hermetic tests; mock ONLY external boundaries (GitHub/llama/network/FS).
  Run on real agent units via `make test-agents-unit` (live llama) and `make test-agents-unit-mock`.
- `agents/agentics/tests/integration/` — integration + e2e (`@pytest.mark.e2e`, `@pytest.mark.slow`,
  `@pytest.mark.integration`). Live-llama tests skip cleanly on `LLAMA_HOST` absence; public
  GitHub reads run token-less. The standing e2e gates are `test_ticket20_*`, `test_ticket22_*`,
  `test_greetings_*` (see `openspec/specs/task-driven-ts-generation-e2e`).
- `agents/agentics/tests/fixtures/` — shared mocks (circuit breaker, GitHub/LLM responses, scenarios).
- `fix_integration_tests.py` / `scripts/test_suite_validation.py` — suite hygiene helpers.

See also (under `docs/architecture/`): `docs/architecture/LLM_CODE_VALIDATION.md` (validation
framework), `docs/architecture/ARCHITECTURE_DEPENDENCY_MANAGEMENT.md` (dependency resolution),
`docs/architecture/TEST_SUITE_README.md` (test suite guide),
`docs/architecture/INTEGRATION_TEST_PLAN.md` (integration coverage plan).

## 4. The OpenSpec loop (the coordinating discipline)

The pipeline above does **not** run in isolation — it is wrapped by the OpenSpec loop /
harness, which is the operational "how the whole thing is run and verified" reference
(`docs/openspec-engineering-loop-harness.md`). In one sentence: **propose → generate → verify
→ archive.**

1. **Propose.** A request becomes an OpenSpec change (`openspec new change <name>`): a
   `proposal.md`, a checkbox `tasks.md`, and `specs/<capability>/spec.md` deltas. `openspec
   validate` must be green before any code is generated. The change is the source of truth.
2. **Generate.** `make run-agentics CHANGE=<name>` runs the pipeline (§3) against the local
   change's specs, deterministically merging generated TS/tests into `src/main.ts` /
   `src/__tests__/main.test.ts` (never committing).
3. **Verify.** The closed loop re-runs `make build-app` + `make test-app` and walks every spec
   requirement; on failure it self-corrects (fix the spec, restore baseline, re-run) until the
   gate is green (behaviours B1–B6, B18).
4. **Archive.** `openspec archive <name>` merges accepted specs into `openspec/specs/`, leaving
   git and generated TS untouched. Work is recorded in `agent-wiki/` (see `record-work` skill /
   `openspec/specs/record-work`).

Durable behaviours **B1–B25** enforced by the loop (backup-before-generate, omission guard,
no-commit/no-push, B9 permission floor, HITL opt-in, doc-sync B8, etc.) are defined in the
harness reference and in `AGENTS.md` — that is the authoritative behavioural contract for the
whole system.

## 5. Execution & boundaries

- **Docker compose only**: `containers/*` + `docker-compose-files/*`; rootless nerdctl. The repo is
  mounted at `/project`; the agentic code runs from `/app`. Resolve the project root by probing for a
  directory containing `openspec/changes` (never a fixed relative depth) (B19).
- **Permissions floor (B9)**: `make b9-perms` applies `chmod -R a+rX` (read) + `chmod -R a+rwX`
  (write targets) so the remapped container uid can read/write.
- **No git commit/push (B4/B14)**: the pipeline writes/merges TS + spec files only; committing is a
  deliberate, separate human action.

## 6. Relationship to the other docs

- This file (`docs/AGENTIC_ARCHITECTURE.md`) describes **what the system is and how it is
  structured** — plugin surface (§2), generator pipeline (§3), and the loop that coordinates them (§4).
- The operational "how the whole loop is run and verified" reference is
  `docs/openspec-engineering-loop-harness.md` (durable behaviours B1–B25).
- `AGENTS.md` is the agent-execution manual, kept in sync with the harness reference per B8.
- `docs/architecture/*` holds the narrower design docs (dependency management, LLM code
  validation, test-suite guide, integration test plan) linked from §3.6.
- `README.md` is the user-facing entry point: it gives the helicopter view and the per-command
  Usage, and links here for the architecture.
