# Proposal: ReadmeDocsSection

## Why

After the docs reorganization (`reorganize-architecture-docs` + the earlier
`update-the-architecture-documentation`), the repository's documentation now has a clear layout:
`docs/AGENTIC_ARCHITECTURE.md` is the canonical entry point for the Python agentic pipeline,
`docs/architecture/` holds the design docs, and `docs/openspec-engineering-loop-harness.md` (plus
`docs/openspec-loop-harness-guide.md`) describe the OpenSpec harness/loop engineering. But the
`README.md` has **no Documentation section at all** — a contributor landing on the repo has no map
to these docs. This change adds a concise Documentation section to `README.md` so the new layout is
discoverable and the links stay correct.

## What Changes

- Add a `## Documentation` section to `README.md` (placed after the plugin feature overview / before
  or near Installation) listing the key docs with one-line descriptions and correct relative links:
  - `docs/AGENTIC_ARCHITECTURE.md` — canonical architecture of the Python agentic pipeline.
  - `docs/architecture/` — design docs (dependency management, LLM code validation, test suite,
    integration test plan).
  - `docs/openspec-engineering-loop-harness.md` — harness + loop engineering (OpenSpec workflow,
    durable behaviours B1–B21).
  - `AGENTS.md` — the agent execution manual for this OpenSpec-driven repo.
- Link text MUST use the post-reorganization paths (no `docs/ARCHITECTURE_REFACTOR.md` or
  `agents/agentics/*.md` references, since those were moved/removed).
- No Python source, Makefile, or generated TS is touched; documentation only.

## Capabilities

- `readme-docs` (new): the README provides an accurate, up-to-date map of the project documentation.

## Impact

- Documentation only — no change to the loop-harness gates, the deterministic floor, or generated
  TS/test code (B4/B14: no git commit/push).
- MUST NOT regress: `make loop-unit` / `make loop-collect` still green (no Python source touched).
