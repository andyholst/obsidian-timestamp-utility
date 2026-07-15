# Proposal: FalseSkipAuditAndRootFix

## Why
The user asked to verify `make loop-harness` and to evaluate every **skipped** agentic test: is the
skip *actually* true (dependency genuinely absent), or is it a **false skip** (the dependency IS
present but the test wrongly skips)? Two classes of false skips were found, both rooted in the
integration container's mount layout:

1. **`/app/src` shadowing** — `docker-compose-files/agents.yaml` binds the agentics Python source
   onto `/app/src`, which **shadows** the repo's own `src/` (TypeScript) inside the integration
   container. `test_change_driven_ts_generation_e2e.py` resolved the repo root to `/app` (where
   `src/main.ts` is absent) and skipped with "No src/main.ts in repo". The same shadowing made
   `_repo_root()` return `/app`, so `make_seeded_project_root` copied nothing into the seeded temp
   dir, which made `HAS_TS_TESTS=False` and silently skipped `test_post_test_runner_agent_integration.py`
   and `test_composable_workflows_integration.py::test_integration_testing_workflow_phase`.
2. **Stale "Dagger" skip reason** — `test_backup_feature.py` skips with "Dagger container
   limitation", but this repo has NO Dagger (AGENTS.md: "No Dagger, no MCP: docker compose only").
   The real cause is `BACKUP_DIR` not existing because `_backup_project_files` was called with a
   `PROJECT_ROOT` that did not resolve to a writable repo root.

Fix: make `_repo_root()` prefer the candidate that has BOTH `openspec/changes` AND `src/main.ts`
(unshadowed repo root, e.g. `/project`), fixing ALL the shadowing false-skips at once. Re-evaluate
the backup skips against the real container.

## What Changes
- `agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py` — `_repo_root()`
  prefers a candidate containing `src/main.ts` (unshadowed `/project`).
- `agents/agentics/tests/integration/_e2e_helpers.py` — `make_seeded_project_root` /
  `plugin_ts_tests_present` now resolve the real TS scaffold via the fixed `_repo_root()`.
- `test_backup_feature.py` — replace the stale "Dagger" reason; skip only when `BACKUP_DIR` truly
  cannot be created (and is actually unreachable), not on a stale assumption.
- `AGENTS.md` (+ skill mirror) — tighten the loop-harness gate description (B17/B20) to state that
  skips MUST be evaluated for truthfulness, and that the integration container mounts the repo root
  at BOTH `/app` and `/project` with `/app/src` shadowing the TS source (so root resolution must
  prefer the unshadowed mount).
- `Makefile` `docker_run` — fix the temp-file indirection (`printf '%s\n' '$(1)'` split quoted
  filters like `TEST_FILTER='-m e2e'` into separate tokens, breaking `make test-agents-e2e` with
  `Error 127`); use a heredoc so the filter passes intact.

## Capabilities
- `loop-harness-integrity` (new): the loop gate must not report green on false skips; root
  resolution must be shadow-aware; `docker_run` must pass filters intact.

## Impact
- More integration/e2e tests actually RUN (not falsely skip) on the host, increasing real coverage.
- `make test-agents-e2e` / `loop-e2e` no longer Error 127.
- AGENTS.md + skill stay the authoritative description of the mount layout (B8 sync).
