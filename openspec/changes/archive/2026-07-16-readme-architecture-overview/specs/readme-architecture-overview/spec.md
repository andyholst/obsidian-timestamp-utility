## ADDED Requirements

### Requirement: README presents a helicopter-view system overview
The `README.md` MUST contain a top-level "What this project is" overview section placed
immediately after the document title that frames the repository as a two-sided system: an
Obsidian TypeScript plugin (the nine user-facing commands) and a Python agentic pipeline
that generates that plugin's code from OpenSpec changes, coordinated by the OpenSpec
loop/harness. The overview MUST link to `docs/AGENTIC_ARCHITECTURE.md` as the full-system
architecture reference.

#### Scenario: a new reader gets the system shape from the top
- **WHEN** a reader opens `README.md`
- **THEN** the section after the title explains, in one screen, what the plugin does for an
  Obsidian user and how the agentic pipeline + OpenSpec loop build and maintain it, with a
  working link to the architecture document.

### Requirement: Architecture document represents the whole system in detail
`docs/AGENTIC_ARCHITECTURE.md` MUST describe the entire two-sided system, not only the
Python pipeline. It MUST cover: (a) a system-level overview of the plugin + pipeline + the
OpenSpec loop that connects them; (b) the plugin surface — the nine registered command
`id`s, their modals, the `src/*.ts` file layout, and the rollup build to `dist/main.js`;
(c) the agentic pipeline (entry points, module/agent map, three-phase workflow,
deterministic merge floor, test layout); and (d) the OpenSpec loop/generate → verify →
archive discipline, pointing at `docs/openspec-engineering-loop-harness.md` for the
authoritative B1–B25 behaviour reference.

#### Scenario: architecture doc covers plugin, pipeline, and loop
- **WHEN** a reader opens `docs/AGENTIC_ARCHITECTURE.md`
- **THEN** it contains a system overview, a plugin-surface section with the nine command
  `id`s and build output, the retained pipeline detail, and a loop section linking to the
  harness reference — and no section still claims the doc only covers the Python pipeline.

### Requirement: Documentation change does not regress the agentic suite
Because this change is documentation-only (`.md` files under `README.md` and
`docs/AGENTIC_ARCHITECTURE.md`), it MUST NOT alter any TypeScript or Python source, any
import path, or any build behaviour.

#### Scenario: no source or build regression
- **WHEN** the README and architecture doc are updated
- **THEN** no `*.ts` / `*.py` file is changed and the existing build + agentic gates remain
  unaffected.

## ADDED Acceptance Criteria

- `README.md` contains a "What this project is" overview section after the title with a
  working link to `docs/AGENTIC_ARCHITECTURE.md`.
- `docs/AGENTIC_ARCHITECTURE.md` contains a system overview, a plugin-surface section
  listing the nine command `id`s and the `dist/main.js` build, and an OpenSpec-loop section
  linking to `docs/openspec-engineering-loop-harness.md`.
- `openspec validate readme-architecture-overview` returns "is valid".
