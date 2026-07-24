## Why

The `docker_run` macro in the Makefile was overly complex: it used `define` blocks with
heredocs, nested `if`/`else` for TTY detection, and required `script -qec` with temp files
to allocate PTYs for `nerdctl compose run` on macOS. This was fragile, hard to debug, and
produced confusing error messages. Additionally, `make stop-containers` was killing honcho
containers (it filtered by container name prefix on hex IDs), and there was no `nuke-all`
target for full cleanup.

The fix: **replace the `docker_run` macro with a simple shell script wrapper** (`scripts/docker_run.sh`) that:
- Detects `nerdctl` vs `docker` at runtime
- Allocates PTY via `script -q /dev/null` for nerdctl (macOS), skips for docker (Linux)
- Handles `--rm` omission for nerdctl (nerdctl auto-removes, no `--rm` flag)
- Is bash 3.2 compatible (macOS default — no associative arrays)

## What Changes

- **Delete the `docker_run` `define` macro** from the Makefile (25+ references).
- **Add `scripts/docker_run.sh`**: PTY-aware wrapper for `docker compose` / `nerdctl compose run`.
- **Add `DOCKER` variable**: simple `nerdctl compose` / `docker compose` detection at Makefile level.
- **Add `DOCKER_BUILD` variable**: `nerdctl` / `docker` for image builds.
- **Fix `tools.yaml`**: use pre-built image with `pull_policy: never`, named volume for node_modules
  (avoids host darwin-arm64 node_modules overwriting container linux-amd64 bindings).
- **Fix `run-loop-harness.sh`**: replace `declare -A` (bash 4+) with flat string accumulation (bash 3.2).
- **Fix `make stop-containers`**: use label filter `--filter 'label=com.docker.compose.project!=honcho'`
  instead of `grep -v '^honcho-'` on container IDs.
- **Add `scripts/nuke-all-containers.sh`**: platform-agnostic nuclear cleanup (stop/remove all containers,
  networks, volumes, images) with timeout guards on all `nerdctl` calls.
- **Add `make nuke-containers`** and legacy `nuke-all-containers` targets.
- **Fix `run-loop-harness.sh`**: macOS compatibility (gdate/gstat, calc_elapsed, stop_loop_containers).

## Capabilities

### New Capabilities
- `macos-nerdctl-pipeline`: All Makefile compose targets run via `scripts/docker_run.sh` wrapper,
  which detects `nerdctl compose` (macOS) vs `docker compose` (Linux) and handles PTY/TTY requirements.
  Includes `make stop-containers` honcho exclusion fix, `make nuke-containers` for full cleanup,
  and `run-loop-harness.sh` bash 3.2 compatibility.

### Modified Capabilities
- `docker-make-pipeline` (archived): The prior change removed Dagger; this refinement makes
  the docker-compose pipeline **macOS-compatible** by replacing the complex `docker_run` macro
  with a simple script wrapper.

## Impact

- `Makefile` — removes `docker_run` define, adds `DOCKER`/`DOCKER_BUILD` variables.
- `scripts/docker_run.sh` — new PTY-aware wrapper (106 lines, bash 3.2 compatible).
- `scripts/run-loop-harness.sh` — bash 3.2 compatibility fixes, macOS date/stat helpers.
- `docker-compose-files/tools.yaml` — pre-built image + named volume for node_modules.
- `containers/npm/Dockerfile` — minor adjustments for the new compose layout.
- `scripts/nuke-all-containers.sh` — new platform-agnostic nuclear cleanup script.
- Test fixtures — doc-sync fixture updates for stage order changes.
