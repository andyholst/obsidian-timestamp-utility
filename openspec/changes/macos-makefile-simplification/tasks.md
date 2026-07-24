# Tasks

## 1. Remove unnecessary SHELL override
- [x] 1.1 Delete lines 1-7: `SHELL := /opt/homebrew/bin/bash` block (unnecessary since we're on bash 5.2+)
- [x] 1.2 Verify Makefile still works without SHELL override

## 2. Replace python3 scripts/docker_run.py with inline $(DOCKER) calls
- [x] 2.1 Each loop stage target currently calls `python3 scripts/docker_run.py docker-compose-files/...` (140 lines of boilerplate)
- [x] 2.2 Replace with direct `$(DOCKER) -f docker-compose-files/...` calls
- [x] 2.3 Add `script -q /dev/null` wrapper only for nerdctl PTY requirement on macOS
- [x] 2.4 Update all targets using docker_run.py: build-app, test-app, changelog, changelog-format, bump-from-changelog, lint-python, format, test-agents-unit, test-agents-unit-mock, test-agents-integration, test-check-docs-sync, loop-collect, loop-e2e, loop-integration, loop-release-tests, check-docs-sync, phase7-archive steps 1/3 and 3/3, run-agentics

## 3. Simplify loop-harness to sequential make calls
- [x] 3.1 Delete `scripts/run-loop-harness.sh` (343 lines of boilerplate: timeouts, heartbeat, kill logic)
- [x] 3.2 Replace `make loop-harness` with sequential `$(MAKE)` calls for each stage
- [x] 3.3 Each stage already has its own target → just call them in order
- [x] 3.4 Add simple echo/exit code reporting instead of complex summary tracking

## 4. Delete unnecessary shell scripts and Python wrappers
- [x] 4.1 Delete `scripts/run-loop-harness.sh` (343 lines) — replaced by inline make targets
- [x] 4.2 Delete `scripts/docker_run.py` (140 lines) — replaced by inline $(DOCKER) calls
- [x] 4.3 Keep: `ts_test_floor.sh`, `nuke-all-containers.sh`, `scaffold-openspec-change.sh`, `gen_changelog.sh` (all have real logic beyond container running)

## 5. Update OpenSpec change documentation
- [ ] 5.1 Update proposal.md to reflect simplified approach (no shell scripts, no Python wrappers)
- [ ] 5.2 Update capabilities description (remove "macos-nerdctl-pipeline", simplify to "inline-docker-calls")

## 6. Verify the full pipeline
- [x] 6.1 `make build-app` succeeds via inline $(DOCKER) calls ✅ exit 0
- [x] 6.2 `make test-app` passes via inline $(DOCKER) calls ✅ exit 0, 65 tests passed
- [x] 6.3 `make loop-harness` runs all stages (sequential make calls)
- [ ] 6.4 `openspec validate macos-makefile-simplification` passes
- [ ] 6.5 `make check-docs-sync` passes (no drift)

## 7. Commit and push frequently
- [ ] 7.1 Commit each logical change group (not all at once)
- [ ] 7.2 Push to `feat/macos-makefile-simplification` regularly
- [ ] 7.3 Create OpenSpec change BEFORE pushing (per B15 / request intake gate)
