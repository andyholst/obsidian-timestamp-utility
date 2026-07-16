# Tasks: run the secret-scanner TEST SUITE as a loop stage; keep the SCAN in the hook

## Why
The loop ran `loop-secret-scan` (a gitleaks scan of the tree) but never exercised the
secret-scanner's own pytest suite. Decision: the **scan** belongs in the pre-commit hook +
CI (it already guards every commit there); the **tests** belong in the loop so a regression
in `scripts/secret_scanner.py` / `.gitleaks.toml` is caught on every loop run.

## Tasks
- [x] 1. Add `loop-secret-scan-tests` Makefile stage: builds `secret-scan-tests-image`
      and runs `tests/test_secret_scanner*.py` inside the `gitleaks-tests` container
      (docker compose only, B9, real gitleaks, no mocks).
- [x] 2. Create `docker-compose-files/gitleaks-tests.yaml` (service `gitleaks-tests`,
      mounts repo at `/src`, runs pytest entrypoint).
- [x] 3. Wire `loop-secret-scan-tests` into `scripts/run-loop-harness.sh`: add to
      `STAGES` (after `loop-test-app`, before `check-docs-sync`), `STAGE_TIMEOUT`,
      and `stage_desc`; REMOVE `loop-secret-scan` from the loop chain.
- [x] 4. Demote `loop-secret-scan` to a standalone on-demand target (not a loop stage);
      the scan stays in `git-hooks/pre-commit` + `commit-msg` + CI.
- [x] 5. Update the B8 canonical chain in AGENTS.md, `hermes/skills/openspec-loop-harness.md`,
      and `docs/openspec-engineering-loop-harness.md` (scan→hook, tests→loop).
- [x] 6. Write this OpenSpec change via `openspec new change` (B15) + validate.
- [x] 7. `make check-docs-sync` (B8) passes (no drift).
- [x] 8. `openspec validate secret-scanner-loop-tests` passes.
- [x] 9. Run `loop-secret-scan-tests` (containerized) — all secret-scanner tests PASS.
- [x] 10. Run `loop-secret-scan` (on-demand) — repo scan still clean/green.
