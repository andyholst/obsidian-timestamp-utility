## Why

The agentic pipeline's Python code (17,342 LOC across 47 modules) has grown well beyond what the
harness, loop-engineering, and OpenSpec engineering model actually requires. The codebase was
built feature-by-feature without a unifying simplification pass, so it now carries:

- **Parallel/duplicate generation stacks** — 5 generator-shaped classes
  (`CodeGeneratorAgent`, `ToolIntegratedCodeGeneratorAgent`, `CollaborativeGenerator`,
  `ToolIntegratedAgent`, `GeneratorAgent`) where the harness needs exactly ONE generation path
  (one generator + the `CodeIntegratorAgent` deterministic floor).
- **Unwired heavy modules** — `code_validator.py` (1,209 LOC) is imported by **nothing** in the
  live graph (`agentics.py` / `composable_workflows.py` / `workflows.py`); `test_suite.py` (1,537
  LOC) is only reachable from its own unit test, not the agentic loop.
- **Redundant orchestration machinery** — `composable_workflows.py` (1,108 LOC) wraps the graph in
  LangGraph + `AgentComposer` + 6 state adapters (`state_adapters.py`, 289 LOC) for a flow the
  harness describes as a simple, bounded fetch → (seed local OpenSpec) → generate → integrate →
  test self-correct loop. The file even has duplicate imports (`import os` twice, `Runnable`
  imported twice) — concrete overcomplexity.
- **Many thin agent classes** (24 `BaseAgent` subclasses) where several are vestigial or
  near-identical (e.g. `PreTestRunnerAgent` vs `PostTestRunnerAgent`, `CodeReviewerAgent` vs
  `CodeValidator` vs `LlmValidator`).

The `ticket20`/`ticket22` e2e tests are our **proof of concept**: they drive the pipeline end to
end and must stay green. The goal of this change is NOT to add behaviour — it is to **reduce the
complexity of the Python agentic code so it actually matches the harness/loop/OpenSpec model**,
while keeping observable behaviour identical (same generated TS, same e2e result). The OpenSpec
CLI (`openspec new change`) is the source of truth for this change's structure (B8 / §3.3).

## What Changes

- Analyze the existing Python agentic codebase and classify every module as: (a) aligned with
  harness/loop/OpenSpec engineering, (b) duplicated/parallel and safe to consolidate, or
  (c) unwired dead weight safe to remove. **Classification is now EVIDENCE-BASED (2026-07-14):** an
  AST import-reachability BFS from the `agentics` entry + a live `add_node` scan of
  `ComposableWorkflows` shows the live loop runs only 8 graph nodes, while 6 agents are
  *registered-but-unwired* and 2 modules are import-orphans — see `tasks.md` §6.
- Heavily slim the misaligned code: remove unwired modules, consolidate parallel generator/validator
  stacks into the single path the harness describes (the `CodeIntegratorAgent` deterministic floor),
  and delete redundant orchestration indirection (duplicate state adapters, double imports).
- Keep behaviour identical: the `CodeIntegratorAgent` deterministic floor remains the sole writer of
  generated TS; `fetch_issue_agent.py` still seeds a local OpenSpec change via the CLI; generation
  still produces the same `src/main.ts` / `src/__tests__/main.test.ts`.
- Update the OpenSpec change files (`tasks.md`) as findings accumulate, driving any code edits
  through `openspec_loader` / the agentic code the same way the harness does — and re-run the
  pipeline/e2e to confirm the same behaviour.

## Capabilities

### New Capabilities
- `python-agentic-slim-refactor`: Reduces the agentic Python to match harness/loop/OpenSpec
  engineering — one generation path, no unwired modules, no redundant orchestration — with
  behaviour preserved and e2e (ticket20/ticket22) still green.

### Modified Capabilities
<!-- No existing spec-level behavior changes beyond slimming the implementation. -->

## Impact

- Affected code: `agents/agentics/src/**` (analysis + removal/consolidation of dead/parallel modules;
  cleanup of `composable_workflows.py` duplicate imports and redundant adapters).
- Affected tests: unit + integration suites must stay green; the `ticket20`/`ticket22` e2e tests are
  the regression gate (B1/B2/B3/B4/B5) and MUST remain passing.
- Affected systems: the agentic pipeline (`make run-agentics`), container images (smaller surface),
  and the OpenSpec CLI workflow (this change itself is scaffolded via `openspec new change`).
