# Tasks

- [x] 1.1 Write `scripts/ts_test_floor.sh` that computes 4 metrics (describe count, leaf it/test count, jest-collected total, addCommand count) for BOTH `origin/main` and the current branch, and exits non-zero if any current metric < baseline.
- [x] 1.2 Make `scripts/ts_test_floor.sh` hermetic: reads `origin/main` (fallback `main`) via `git show`, runs `npx jest --listTests`/`--collectOnly` locally, never writes the tree, never needs network/Ollama.
- [x] 1.3 Add `loop-ts-floor` Makefile target that invokes `scripts/ts_test_floor.sh` and FAILS (non-zero) on any drop.
- [x] 1.4 Wire `loop-ts-floor` into `scripts/run-loop-harness.sh` as an early hermetic stage (before/with loop-collect) and add a STAGE_TIMEOUT entry; non-zero marks the run FAILED.
- [x] 2.1 Verify the guard locally: `bash scripts/ts_test_floor.sh` passes on the current branch (counts >= origin/main).
- [x] 2.2 Proof-of-failure: temporarily dropped a `describe`/leaf/`addCommand` and confirmed `bash scripts/ts_test_floor.sh` exits non-zero, then restored.
- [x] 3.1 B8-sync: documented the new `loop-ts-floor` stage in AGENTS.md (Phase 6 + hermetic fallback) and `hermes/skills/openspec-loop-harness.md`; the 4 artifacts (Makefile + AGENTS.md + skill + e2e harness) agree on EIGHT stages incl. ts-floor.
- [x] 4.1 `openspec validate strict-ts-test-floor` passes
