# Tasks — readme-architecture-overview

- [x] 1.1 Add a "What this project is" overview section to `README.md` immediately after the
  H1 title, framing the two-sided system (Obsidian TypeScript plugin + Python agentic
  pipeline + OpenSpec loop) in one screen so a new reader gets the helicopter view.
- [x] 1.2 Make the README's Architecture link prominent and accurate (points at
  `docs/AGENTIC_ARCHITECTURE.md` as the full-system architecture reference).
- [x] 2.1 Expand `docs/AGENTIC_ARCHITECTURE.md` §1 (Purpose) into a system-level overview
  describing the two halves (plugin + pipeline) and the OpenSpec loop that connects them.
- [x] 2.2 Add a new "Plugin surface" section to the architecture doc covering the nine
  registered commands (`id`s), their modals, the `src/*.ts` file layout, and the rollup
  build to `dist/main.js` — accurate to `src/main.ts` and `manifest.json` (v0.4.11).
- [x] 2.3 Add a "The OpenSpec loop" section to the architecture doc explaining generate →
  verify → archive, pointing at `docs/openspec-engineering-loop-harness.md` for the
  authoritative B1–B25 behaviour reference.
- [x] 2.4 Keep the existing pipeline detail (entry points, module/agent map, three-phase
  workflow, deterministic merge floor, test layout) intact and repoint section numbers
  so the document reads as a coherent whole-system reference.
- [x] 3.1 Verify the README links resolve (no broken local paths) and the architecture doc
  describes the plugin surface and the loop (not only the Python pipeline).
- [x] 3.2 `openspec validate readme-architecture-overview` passes.
