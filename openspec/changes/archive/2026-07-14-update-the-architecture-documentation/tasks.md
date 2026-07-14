# Tasks

- [x] 1.1 Fill the change `update-the-architecture-documentation` proposal.md / spec.md / tasks.md with the real doc-consolidation intent (moved from template TODOs)
- [x] 2.1 Create `docs/AGENTIC_ARCHITECTURE.md` (module map, three-phase pipeline, deterministic merge floor, test layout)
- [x] 2.2 Move the five Python-agentic docs into `docs/` (keep verbatim; add a top-of-file redirect note where cross-referenced)
- [x] 2.3 Update path references: `.dockerignore` lines 66-68 → `docs/*.md`; `docs/INTEGRATION_TEST_PLAN.md` internal links → relative to `docs/`
- [x] 3.1 B8-sync: confirm AGENTS.md / openspec-loop-harness skill are unaffected (docs-only change, no behaviour change) — note in proposal if any pointer needs updating
- [x] 4.1 VERIFICATION: `make loop-collect` + `make loop-unit` still pass (documentation-only, no Python source touched)
- [x] 5.1 `openspec validate update-the-architecture-documentation` passes
