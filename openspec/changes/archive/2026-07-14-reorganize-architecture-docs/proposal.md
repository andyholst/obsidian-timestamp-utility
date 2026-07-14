# Proposal: ReorganizeArchitectureDocs

## Why

The previous `update-the-architecture-documentation` change moved the Python-agentic docs into a
flat `docs/` folder and added a canonical `docs/AGENTIC_ARCHITECTURE.md`. But the result is still
**messy**: harness docs (`openspec-engineering-loop-harness.md`,
`openspec-loop-harness-guide.md`) and architecture docs sit side-by-side, and several of the
moved "architecture" docs are either **outdated** or **redundant** with the new canonical doc.
The user wants the architecture docs organized into a dedicated `docs/architecture/` subfolder to
keep things neat, and wants genuinely outdated documents removed rather than kept for history.

## What Changes

- Create `docs/architecture/` as the home for all agentic architecture/design docs.
- Move the still-current docs into it:
  - `docs/ARCHITECTURE_DEPENDENCY_MANAGEMENT.md` → `docs/architecture/ARCHITECTURE_DEPENDENCY_MANAGEMENT.md`
  - `docs/LLM_CODE_VALIDATION.md` → `docs/architecture/LLM_CODE_VALIDATION.md`
  - `docs/TEST_SUITE_README.md` → `docs/architecture/TEST_SUITE_README.md`
  - `docs/INTEGRATION_TEST_PLAN.md` → `docs/architecture/INTEGRATION_TEST_PLAN.md` (anchors fixed)
- **Remove the outdated `docs/ARCHITECTURE_REFACTOR.md`**: it describes the agentic refactor as a
  *proposed* change with "current architecture issues", but that refactor is already merged and is
  now the live architecture described by `docs/AGENTIC_ARCHITECTURE.md`. Keeping it is misleading.
  All inbound links to it (`LLM_CODE_VALIDATION.md`, `ARCHITECTURE_DEPENDENCY_MANAGEMENT.md`,
  `INTEGRATION_TEST_PLAN.md`, `AGENTIC_ARCHITECTURE.md`) are repointed to `docs/AGENTIC_ARCHITECTURE.md`.
- Fix `docs/architecture/INTEGRATION_TEST_PLAN.md` stale `file:line` anchors (they now point at the
  wrong lines: `state.py:27` → 41, `tools.py:12` → 13, `tools.py:58` → 60, `agent_composer.py:15` → 16).
- Update `docs/AGENTIC_ARCHITECTURE.md` "See also" to reference the `docs/architecture/` paths (and
  drop the removed `ARCHITECTURE_REFACTOR.md` link).
- Update `.dockerignore` (the `docs/ARCHITECTURE_REFACTOR.md` / `LLM_CODE_VALIDATION.md` /
  `TEST_SUITE_README.md` ignores) to the new `docs/architecture/` locations.

## Capabilities

- `architecture-doc` (extends existing): architecture documentation is now organized under
  `docs/architecture/` and free of outdated/redundant files.

## Impact

- Documentation only — no change to the loop-harness gates, the deterministic floor, or generated
  TS/test code (B4/B14: no git commit/push).
- MUST NOT regress: `make loop-unit` / `make loop-collect` still green (no Python source touched,
  only `.md` + `.dockerignore`).
