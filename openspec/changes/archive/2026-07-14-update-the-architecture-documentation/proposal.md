# Proposal: UpdateTheArchitectureDocumentation

## Why

The Python agentic pipeline (`agents/agentics/`) carries several architecture/design docs that
live next to the code (`agents/agentics/ARCHITECTURE_REFACTOR.md`,
`ARCHITECTURE_DEPENDENCY_MANAGEMENT.md`, `LLM_CODE_VALIDATION.md`, `TEST_SUITE_README.md`, and
`agents/agentics/tests/integration/INTEGRATION_TEST_PLAN.md`). There is no single, canonical
architecture document for the agentic subsystem, and the docs are scattered across the tree. The
user wants the architecture documentation for the Python agentic code consolidated into the `docs/`
folder (mirroring `docs/openspec-engineering-loop-harness.md`), with the existing Python-agentic
docs moved/updated into that folder and a new authoritative `docs/AGENTIC_ARCHITECTURE.md`
describing the module map, the three-phase pipeline, and the deterministic floor.

## What Changes

- Add `docs/AGENTIC_ARCHITECTURE.md`: the canonical architecture reference for the agentic pipeline
  (entry points, module map, three-phase workflow, deterministic merge floor, testing layout).
- Move the five Python-agentic docs into `docs/` (kept verbatim, with a top-of-file redirect note
  where other files link to them):
  - `agents/agentics/ARCHITECTURE_REFACTOR.md` → `docs/ARCHITECTURE_REFACTOR.md`
  - `agents/agentics/ARCHITECTURE_DEPENDENCY_MANAGEMENT.md` → `docs/ARCHITECTURE_DEPENDENCY_MANAGEMENT.md`
  - `agents/agentics/LLM_CODE_VALIDATION.md` → `docs/LLM_CODE_VALIDATION.md`
  - `agents/agentics/TEST_SUITE_README.md` → `docs/TEST_SUITE_README.md`
  - `agents/agentics/tests/integration/INTEGRATION_TEST_PLAN.md` → `docs/INTEGRATION_TEST_PLAN.md`
- Update the path references that pointed at the old locations:
  - `.dockerignore` lines 66-68 (the three `agents/agentics/*.md` ignores) → updated to `docs/*.md`.
  - `docs/INTEGRATION_TEST_PLAN.md` internal links to `ARCHITECTURE_REFACTOR.md` → relative to `docs/`.
  - Test docstrings that name the docs by filename (prose, not path) stay valid.

## Capabilities

- `architecture-doc` (new): canonical, consolidated architecture documentation for the Python
  agentic pipeline, located in `docs/`.

## Impact

- Documentation only — no change to the loop-harness gates, the deterministic floor, or any
  generated TypeScript/test code (B4/B14: no git commit/push from this change).
- MUST NOT regress: `make loop-unit` / `make loop-collect` still green (this change touches no
  Python source, only `.md` + `.dockerignore`); no module import paths change.
