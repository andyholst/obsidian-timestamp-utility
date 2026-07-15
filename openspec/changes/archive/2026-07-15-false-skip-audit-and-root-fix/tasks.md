# Tasks

## audit + root fix (real root cause found)
- [x] 1.1 Diagnose the false skip: `test_change_driven_modal_generation_is_persistent_and_runnable`
      skipped with "No src/main.ts in repo". Root cause: the `integration-test-agents` compose service
      mounted the repo only at `/app` (where `/app/src` is SHADOWED by the agentics Python bind-mount)
      and did NOT mount `/project`. So `_repo_root()` could never reach the unshadowed `src/main.ts`.
      VERIFY: ran the exact compose container -> `/project` absent, `/app/src/main.ts` absent -> skip.
- [x] 1.2 Fix `docker-compose-files/agents.yaml`: add `- ..:/project` to `integration-test-agents`
      volumes, so the unshadowed repo root (with real `src/main.ts` + `src/__tests__/main.test.ts`) is
      reachable. This also un-skips `test_post_test_runner_agent_integration.py` and
      `test_composable_workflows_integration.py::test_integration_testing_workflow_phase` (their
      `HAS_TS_TESTS` depended on `make_seeded_project_root` -> `_repo_root()` -> `/project`).
- [x] 1.3 `_repo_root()` already correctly prefers a candidate containing BOTH `openspec/changes` AND
      `src/main.ts` (unshadowed `/project`); with `/project` now mounted it resolves correctly.
- [x] 1.4 Fix `Makefile` `docker_run` temp-file indirection: `printf '%s\n' '$(1)'` split quoted
      filters (`TEST_FILTER='-m e2e'`) into separate tokens -> `Error 127`. Replaced with a heredoc so
      the filter passes intact. VERIFY: `make test-agents-e2e` no longer `Error 127`.

## backup-feature skips (evaluated: NOT false skips)
- [x] 2.1 Re-evaluate `test_backup_feature.py` "Dagger container limitation" skips. VERDICT: they are
      NOT false skips — with the default `PROJECT_ROOT=/tmp/obsidian-project` (writable) all 10 backup
      tests PASS (verified in-container). The reason string is stale/misleading (this repo uses docker
      compose, not Dagger) but the skip only triggers when `BACKUP_DIR` genuinely cannot be created.
      Action: fixed the stale reason wording (see 2.2). `_backup_project_files` still silently swallows
      errors (observability gap) — noted, low priority.

## loop-harness gate tightening (B8)
- [x] 3.1 AGENTS.md B17 rule 5: a green gate MUST NOT rely on FALSE skips; after every loop run inspect
      the skip list and confirm each reason is true; the integration container mounts repo at `/app`
      (shadowed `/app/src`) AND `/project` (unshadowed) and `_repo_root` must prefer `/project`.
      Mirrored in the skill (B8 sync). VERIFY: grep confirms rule 5 in both files.
- [x] 3.2 Add an explicit loop-harness rule: a skip whose dependency is present is a GATE DEFECT.

## verification
- [x] 4.1 `make loop-collect` + `make loop-unit` hermetic gates GREEN (already verified: 525/525).
- [x] 4.2 `make loop-e2e` now RUNS the previously-skipped test (not skip) after the `/project` mount fix.
      RUN and confirm `test_change_driven_modal_generation_is_persistent_and_runnable` PASSES.
- [x] 4.3 `openspec validate false-skip-audit-and-root-fix` passes.
