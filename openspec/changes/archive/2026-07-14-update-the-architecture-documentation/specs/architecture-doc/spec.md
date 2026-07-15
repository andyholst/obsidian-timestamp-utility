# architecture-doc Specification

## ADDED Requirements

### Requirement: Canonical agentic architecture document exists in docs/
The repository MUST contain `docs/AGENTIC_ARCHITECTURE.md` as the single canonical architecture
reference for the Python agentic pipeline. It MUST cover the entry points (`agents/agentics/src/agentics.py`,
`composable_workflows.py`), the module/agent map, the three-phase workflow (issue processing →
code generation → integration & testing), the deterministic merge floor (`CodeIntegratorAgent`),
and the test layout (`tests/unit`, `tests/integration`, `tests/fixtures`).

#### Scenario: architecture doc present and structured
- **WHEN** a reader opens `docs/AGENTIC_ARCHITECTURE.md`
- **THEN** it describes the agentic module map, the three-phase pipeline, and the deterministic
  floor in imperative, factual prose (no TODO placeholders).

### Requirement: Existing Python-agentic docs are consolidated into docs/
The five Python-agentic design docs MUST reside in `docs/` (not scattered under `agents/agentics/`):
`ARCHITECTURE_REFACTOR.md`, `ARCHITECTURE_DEPENDENCY_MANAGEMENT.md`, `LLM_CODE_VALIDATION.md`,
`TEST_SUITE_README.md`, and `INTEGRATION_TEST_PLAN.md`. Internal links between them MUST remain
valid after the move.

#### Scenario: docs moved and links intact
- **WHEN** the docs are moved from `agents/agentics/` into `docs/`
- **THEN** each moved file exists under `docs/`, no broken internal relative links remain, and any
  repo file that referenced the old path is updated (e.g. `.dockerignore`).

### Requirement: Ignore rules and cross-references updated
Files that referenced the old doc locations MUST be updated so the move does not break builds or
leave stale paths. Specifically `.dockerignore` MUST ignore the moved `docs/*.md` paths instead of
the old `agents/agentics/*.md` paths.

#### Scenario: dockerignore updated
- **WHEN** `.dockerignore` is inspected
- **THEN** it references the `docs/` locations of the moved architecture docs, not the removed
  `agents/agentics/*.md` paths.

### Requirement: Documentation change does not regress the agentic suite
Because this change is documentation-only (`.md` + `.dockerignore`), it MUST NOT alter any Python
source or import path, and the hermetic agentic gates MUST remain green.

#### Scenario: hermetic gates still pass
- **WHEN** `make loop-collect` and `make loop-unit` run after the doc move
- **THEN** they pass (no Python source changed, only documentation and ignore rules).
