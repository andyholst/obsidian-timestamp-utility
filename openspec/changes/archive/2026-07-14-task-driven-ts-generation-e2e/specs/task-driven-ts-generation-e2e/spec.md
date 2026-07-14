# Capability: task-driven-ts-generation-e2e

The pipeline generates TS code + TS tests ONLY from the task supplied as an argument
(`openspec:<change>`), with no hardcoded Python feature logic; an e2e test proves a
timestamp feature is generated correctly and runs.

## ADDED Requirements

### Requirement: Generation is driven only by the task argument
The Python pipeline MUST read the OpenSpec change/task passed as the `openspec:<change>`
argument (via `openspec_loader.load_change`) and feed it to the LLM. It MUST NOT contain
hardcoded Python that emits specific TS feature code (e.g. a branch that writes a fixed
function body). Generation MUST derive entirely from the task/spec text.

#### Scenario: No hardcoded TS emitter
- **WHEN** a reviewer greps the agentic source for TS-body-string emission tied to a feature
- **THEN** none exists; all generation flows from the loaded change text + LLM.

### Requirement: New timestamp feature generated from a task (as an Obsidian Modal)
The pipeline MUST be able to generate a `TimestampModal` (an `obsidian.Modal` subclass) from a
task argument, exposing `getCurrentTimestamp()` (returning a `YYYYMMDD-HHMMSS` string from the
current date/time), and MUST register it as an Obsidian command in `main.ts`
(`this.addCommand({ id: "insert-timestamp", callback: () => new TimestampModal(this.app).open() })`)
without dropping existing logic (omission guard). Like ALL generated TS features, the timestamp
helper MUST be a Modal wired as a command, never a bare function/utility.

#### Scenario: Timestamp Modal generated from task and registered
- **WHEN** the loop runs with a task describing the `YYYYMMDD-HHMMSS` timestamp Modal
- **THEN** the generated TS contains a `TimestampModal` (`obsidian.Modal` subclass) with a working
  `getCurrentTimestamp()`, registered as the `insert-timestamp` command, and existing code is preserved.

### Requirement: e2e test proves task-driven correctness (real call)
A **persistent** integration/e2e test (`agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py`)
MUST invoke the pipeline with the change/task as an argument using a **real** Ollama call, read the
change's `tasks.md` (+`spec.md`) to confirm a Modal-generation task is present, then assert the
generated `src/main.ts` contains an `obsidian.Modal` subclass wired via `this.addCommand(...)`.
The test MUST NOT mock the LLM or hardcode expected TS. This file MUST NOT be removed when the
change is archived (durable behaviour B1). It runs into an isolated temp dir and NEVER commits/pushes (B4).

#### Scenario: e2e validates real generated modal from the task file
- **WHEN** `test_change_driven_ts_generation_e2e.py` runs (real Ollama)
- **THEN** it loads the change's `tasks.md`, runs the pipeline with the change as the argument, and
  asserts the generated `main.ts` contains a Modal subclass registered as a command.

### Requirement: Feature integrated, not omitting existing logic
When integrating the generated timestamp helper, the pipeline MUST merge into `main.ts` /
utility modules (add the command/function) and MUST NOT shrink pre-existing files (omission guard).

#### Scenario: No omission on integration
- **WHEN** the integrator writes the generated timestamp helper
- **THEN** existing commands/functions remain and the output file is not smaller than its backup.

## ADDED Acceptance Criteria

- Grep confirms no hardcoded TS-feature emitter in the pipeline source.
- Generated TS exposes `getCurrentTimestamp()` returning `YYYYMMDD-HHMMSS`.
- `test_task_driven_timestamp_e2e.py` passes with a real Ollama call and validates the format.
- `main.ts`/utility files are not shrunk (omission guard holds).
