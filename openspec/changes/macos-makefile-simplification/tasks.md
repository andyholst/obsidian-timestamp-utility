## 1. Replace docker_run macro with script wrapper
- [x] 1.1 Create `scripts/docker_run.sh` — PTY-aware wrapper for `docker compose`/`nerdctl compose run`
  - Detects nerdctl vs docker at runtime
  - Uses `script -q /dev/null` for nerdctl TTY (macOS), plain run for docker (Linux)
  - Omits `--rm` for nerdctl (auto-removes)
  - Bash 3.2 compatible (no associative arrays)
- [x] 1.2 Add `DOCKER` variable to Makefile (auto-detects nerdctl compose / docker compose)
- [x] 1.3 Add `DOCKER_BUILD` variable to Makefile (nerdctl / docker for image builds)
- [x] 1.4 Replace all 25+ `$(call docker_run, ...)` references with `$(DOCKER) -f ...`
- [x] 1.5 Remove the `docker_run` define macro from the Makefile

## 2. Fix tools.yaml for nerdctl compatibility
- [x] 2.1 Switch app service to pre-built image (`image: docker-compose-files-app:latest`)
- [x] 2.2 Add `pull_policy: never` to avoid architecture mismatch (nerdctl defaults to arm64 on macOS)
- [x] 2.3 Use named volume `npm_modules` for node_modules (preserves linux-amd64 bindings)
- [x] 2.4 Mount source to `/project` (not `/app`) to avoid host node_modules overwriting

## 3. Fix run-loop-harness.sh for bash 3.2 (macOS)
- [x] 3.1 Replace `declare -A` associative arrays with flat string accumulation
- [x] 3.2 Add `get_epoch()`, `calc_elapsed()`, `get_file_size()` with macOS fallbacks
- [x] 3.3 Replace `comm` with `diff` (macOS doesn't have GNU comm)
- [x] 3.4 Add gdate/gstat detection (GNU coreutils if installed, else macOS defaults)
- [x] 3.5 Fix `stop_loop_containers()` to use `diff` instead of process substitution

## 4. Fix stop-containers to exclude honcho properly
- [x] 4.1 Change from `grep -v '^honcho-'` (broken: container IDs are hex strings)
- [x] 4.2 Use `--filter 'label=com.docker.compose.project!=honcho'` (correct: labels identify compose projects)
- [x] 4.3 Verify honcho containers survive `make stop-containers`

## 5. Add nuke-all-containers script and targets
- [x] 5.1 Create `scripts/nuke-all-containers.sh` — platform-agnostic nuclear cleanup
  - Stops/removes ALL containers, networks, volumes, images
  - Timeout guards on all `nerdctl` calls (prevents hanging containerd)
  - Configurable via `HONCHO_COMPOSE` env var (no hardcoded paths)
  - bash 3.2 compatible
- [x] 5.2 Add `make nuke-containers` target (platform-agnostic)
- [x] 5.3 Add legacy `nuke-all-containers` target for backward compatibility

## 6. Verify the full pipeline
- [x] 6.1 `make build-app` succeeds via nerdctl compose
- [x] 6.2 `make test-app` passes via nerdctl compose
- [x] 6.3 `make stop-containers` excludes honcho (honcho stays up)
- [x] 6.4 `make nuke-containers` runs without hanging
- [x] 6.5 `make loop-harness` runs all stages (bash 3.2 compatibility verified)
- [x] 6.6 `openspec validate macos-makefile-simplification` passes
- [x] 6.7 `make check-docs-sync` passes (no drift)

## 7. Commit and push frequently
- [x] 7.1 Commit each logical change group (not all at once)
- [x] 7.2 Push to `feat/macos-makefile-simplification` regularly
- [x] 7.3 Create OpenSpec change BEFORE pushing (per B15 / request intake gate)

## 8. Fix container runtime and lint-python issues
- [x] 8.1 Change docker_run.sh to use `colima nerdctl -- compose` instead of broken `/private/tmp/nerdctl`
- [x] 8.2 Fix lint-python target to use absolute path `/app/src` instead of relative `agents/agentics/src`
- [x] 8.3 Verify `make build-app` passes (11.8s, plugin builds successfully)
- [x] 8.4 Verify `make test-app` passes (65 tests, 3 suites)
- [x] 8.5 Verify `make lint-python` runs and reports real issues (217 ruff warnings)
