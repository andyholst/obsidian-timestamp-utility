# Design — task-driven-ts-generation-e2e

## Principle: task drives generation, never hardcoded Python
The pipeline entry is `python -m prod.agentics openspec:<change>`. `openspec_loader.load_change`
reads `proposal.md` + `tasks.md` + `specs/**` and synthesizes `ticket_content`. The LLM
(code_generator + test_generator) produces the TS from that text. **No Python branch may
emit a specific TS feature body.** If any hardcoded emitter exists, refactor it so generation
is fully prompt/task-driven.

## New feature: current timestamp helper
- Add ONE task to the target change's `tasks.md` (e.g. under `uuid-modal-agentic-generation`
  or a dedicated `timestamp-helper` change):
  "Add `getCurrentTimestamp(): string` to the plugin that returns the current local
  date/time formatted as `YYYYMMDD-HHMMSS`."
- The loop reads this task and generates:
  - a `getCurrentTimestamp()` function (in `main.ts` or a small `src/timestamp.ts` utility),
  - its unit test asserting the `YYYYMMDD-HHMMSS` format (`^\d{8}-\d{6}$`).

## e2e test (real call)
`agents/agentics/tests/integration/test_task_driven_timestamp_e2e.py`:
1. Passes the **task/change as an argument** to the pipeline (real Ollama call, no mock).
2. After generation, loads the generated TS, and validates:
   - `getCurrentTimestamp` exists,
   - calling it (via ts-node/jest or a compiled check) returns a string matching `^\d{8}-\d{6}$`,
   - the generated file is not smaller than its backup (omission guard).
3. Asserts on real output only — no hardcoded expected TS body.

## Relationship to other changes
- Requires `agentic-architecture-test-refactor` (architecture must support fully task-driven
  generation; integrator must merge not replace).
- Satisfies `agentic-tests-real-logic` (e2e makes a real Ollama call).

## Verification
- Grep of agentic src shows no hardcoded TS-feature emitter.
- `make run-agentics CHANGE=<timestamp-change>` produces `getCurrentTimestamp()`.
- `test_task_driven_timestamp_e2e.py` passes with a real Ollama call.
