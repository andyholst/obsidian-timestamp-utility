# readme-docs Specification

## ADDED Requirements

### Requirement: README documents the documentation layout
`README.md` MUST contain a `## Documentation` section that maps contributors to the repository's
documentation. It MUST link (with correct relative paths) to at least:
- `docs/AGENTIC_ARCHITECTURE.md` — canonical architecture of the Python agentic pipeline.
- `docs/architecture/` — the agentic design docs (dependency management, LLM code validation,
  test suite, integration test plan).
- `docs/openspec-engineering-loop-harness.md` — OpenSpec harness + loop engineering reference.
- `AGENTS.md` — the agent execution manual for this OpenSpec-driven repo.

#### Scenario: documentation section present and correct
- **WHEN** a contributor opens `README.md`
- **THEN** a `## Documentation` section exists listing the docs above with working relative links
  and one-line descriptions, and none of the links point at removed/moved paths
  (`docs/ARCHITECTURE_REFACTOR.md`, `agents/agentics/*.md`).

### Requirement: README links use post-reorganization paths
Every documentation link in `README.md` MUST use the current layout
(`docs/AGENTIC_ARCHITECTURE.md`, `docs/architecture/...`, `docs/openspec-engineering-loop-harness.md`,
`AGENTS.md`). No link may reference the removed `ARCHITECTURE_REFACTOR.md` or the old
`agents/agentics/` doc locations.

#### Scenario: no stale doc links in README
- **WHEN** `README.md` is grepped for documentation references
- **THEN** it contains no link to `ARCHITECTURE_REFACTOR.md` or `agents/agentics/*.md`, and all
  linked doc files exist at the referenced paths.

### Requirement: Documentation change does not regress the agentic suite
Because this change touches only `README.md`, it MUST NOT alter any Python source, Makefile, or
import path, and the hermetic agentic gates MUST remain green.

#### Scenario: hermetic gates still pass
- **WHEN** `make loop-collect` and `make loop-unit` run after the README edit
- **THEN** they pass (no Python source changed).
