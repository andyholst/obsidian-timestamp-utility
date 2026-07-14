# architecture-doc Specification

## MODIFIED Requirements

### Requirement: Canonical agentic architecture document exists in docs/
The repository MUST contain `docs/AGENTIC_ARCHITECTURE.md` as the single canonical architecture
reference for the Python agentic pipeline. It MUST cover the entry points (`agents/agentics/src/agentics.py`,
`composable_workflows.py`), the module/agent map, the three-phase workflow (issue processing →
code generation → integration & testing), the deterministic merge floor (`CodeIntegratorAgent`),
and the test layout (`tests/unit`, `tests/integration`, `tests/fixtures`). All other agentic
design docs MUST live in the dedicated `docs/architecture/` subfolder (not the `docs/` root),
keeping harness docs separate.

#### Scenario: architecture doc present and structured
- **WHEN** a reader opens `docs/AGENTIC_ARCHITECTURE.md`
- **THEN** it describes the agentic module map, the three-phase pipeline, and the deterministic
  floor in imperative, factual prose (no TODO placeholders).

### Requirement: Existing Python-agentic docs are consolidated into docs/
The current Python-agentic design docs MUST reside in the dedicated `docs/architecture/` subfolder
(not the `docs/` root, and not scattered under `agents/agentics/`): `ARCHITECTURE_DEPENDENCY_MANAGEMENT.md`,
`LLM_CODE_VALIDATION.md`, `TEST_SUITE_README.md`, and `INTEGRATION_TEST_PLAN.md`. The outdated
`ARCHITECTURE_REFACTOR.md` (a proposed-refactor artifact superseded by `AGENTIC_ARCHITECTURE.md`)
is removed rather than kept. Internal links between the remaining docs MUST remain valid after the
move, and no remaining doc links to the removed file.

#### Scenario: docs moved and links intact
- **WHEN** the docs are moved from `agents/agentics/` into `docs/architecture/`
- **THEN** each moved file exists under `docs/architecture/`, no broken internal relative links
  remain, any repo file that referenced the old path is updated (e.g. `.dockerignore`), and the
  removed `ARCHITECTURE_REFACTOR.md` is no longer linked from any remaining doc.

### Requirement: Ignore rules and cross-references updated
Files that referenced the old doc locations MUST be updated so the move does not break builds or
leave stale paths. Specifically `.dockerignore` MUST ignore the moved `docs/architecture/*.md`
paths instead of the old `agents/agentics/*.md` or `docs/*.md` paths.

#### Scenario: dockerignore updated
- **WHEN** `.dockerignore` is inspected
- **THEN** it references the `docs/architecture/` locations of the moved architecture docs, not the
  removed `docs/ARCHITECTURE_REFACTOR.md` or old `agents/agentics/*.md` paths.

## ADDED Requirements

### Requirement: Outdated architecture docs are removed, not hoarded
Documents that describe an already-merged refactor as "proposed" (and are superseded by the
canonical architecture doc) MUST be removed rather than kept for history. Their inbound links MUST
be repointed to the canonical `docs/AGENTIC_ARCHITECTURE.md` so no broken links remain.

#### Scenario: ARCHITECTURE_REFACTOR.md is gone and links repointed
- **WHEN** `docs/ARCHITECTURE_REFACTOR.md` (the stale refactor proposal) is removed
- **THEN** no remaining doc links to it; every former reference now points to
  `docs/AGENTIC_ARCHITECTURE.md`.

### Requirement: Remaining docs are accurate (no stale anchors)
Design docs that are kept MUST have correct internal references. Specifically
`docs/architecture/INTEGRATION_TEST_PLAN.md` MUST cite file:line anchors that match the current
source (e.g. `state.py:41`, `tools.py:13`, `tools.py:60`, `agent_composer.py:16`).

#### Scenario: INTEGRATION_TEST_PLAN anchors are correct
- **WHEN** `docs/architecture/INTEGRATION_TEST_PLAN.md` is opened
- **THEN** its `file:line` links resolve to the claimed symbols in the current code.
