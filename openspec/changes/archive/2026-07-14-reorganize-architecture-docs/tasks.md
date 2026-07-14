# Tasks

- [x] 1.1 Fill the change `reorganize-architecture-docs` proposal.md / spec.md / tasks.md with the real subfolder + prune plan
- [x] 2.1 Create `docs/architecture/` and move the 4 current docs (DEPENDENCY_MANAGEMENT, LLM_CODE_VALIDATION, TEST_SUITE_README, INTEGRATION_TEST_PLAN) into it
- [x] 3.1 Remove the outdated `docs/ARCHITECTURE_REFACTOR.md` (superseded by AGENTIC_ARCHITECTURE.md)
- [x] 3.2 Repoint all inbound links to `ARCHITECTURE_REFACTOR.md` → `docs/AGENTIC_ARCHITECTURE.md` (LLM_CODE_VALIDATION.md, ARCHITECTURE_DEPENDENCY_MANAGEMENT.md, INTEGRATION_TEST_PLAN.md)
- [x] 4.1 Fix `docs/architecture/INTEGRATION_TEST_PLAN.md` stale `file:line` anchors to match current source (state.py:41, tools.py:13, tools.py:60, agent_composer.py:16)
- [x] 4.2 Update `docs/AGENTIC_ARCHITECTURE.md` "See also" to `docs/architecture/` paths and drop the removed `ARCHITECTURE_REFACTOR.md` link
- [x] 5.1 Update `.dockerignore` to ignore `docs/architecture/*.md` (remove stale `docs/ARCHITECTURE_REFACTOR.md` / `agents/agentics/*.md` entries)
- [x] 6.1 B8-sync check: confirm AGENTS.md / openspec-loop-harness skill unaffected (docs-only)
- [x] 7.1 VERIFICATION: `make loop-collect` + `make loop-unit` still pass
- [x] 8.1 `openspec validate reorganize-architecture-docs` passes
