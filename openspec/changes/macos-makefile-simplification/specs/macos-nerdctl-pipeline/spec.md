# Capability: macos-nerdctl-pipeline

All Makefile compose targets run via `scripts/docker_run.sh` — a PTY-aware wrapper that
detects `nerdctl compose` (macOS) vs `docker compose` (Linux) and handles terminal
requirements. Includes `make stop-containers` honcho exclusion fix, `make nuke-containers`
for full cleanup, and `run-loop-harness.sh` bash 3.2 compatibility.

## ADDED Requirements

### Requirement: No docker_run define macro
The Makefile MUST NOT contain a `docker_run` `define` macro.

#### Scenario: docker_run macro removed
- **WHEN** the Makefile is searched for `define docker_run`
- **THEN** no match is found.

### Requirement: DOCKER variable detection
The Makefile MUST use a `DOCKER` variable that auto-detects `nerdctl compose` or `docker compose`.

#### Scenario: DOCKER detects nerdctl
- **WHEN** `nerdctl` is in PATH
- **THEN** `DOCKER` expands to `nerdctl compose`.

#### Scenario: DOCKER falls back to docker
- **WHEN** `nerdctl` is NOT in PATH but `docker` is
- **THEN** `DOCKER` expands to `docker compose`.

### Requirement: docker_run.sh wrapper
All compose `run` commands MUST go through `scripts/docker_run.sh` for PTY handling.

#### Scenario: nerdctl gets PTY on macOS
- **WHEN** `docker_run.sh` is called with `nerdctl compose`
- **THEN** it wraps the command in `script -q /dev/null` to allocate a TTY.

#### Scenario: docker runs plain on Linux
- **WHEN** `docker_run.sh` is called with `docker compose`
- **THEN** it runs the command directly without PTY wrapping.

#### Scenario: nerdctl omits --rm
- **WHEN** `docker_run.sh` detects `nerdctl`
- **THEN** it does NOT pass `--rm` (nerdctl auto-removes containers).

### Requirement: tools.yaml pre-built image
The `app` service in `docker-compose-files/tools.yaml` MUST use a pre-built image with `pull_policy: never`.

#### Scenario: No build on every run
- **WHEN** `make build-app` runs via compose
- **THEN** it uses `image: docker-compose-files-app:latest` with `pull_policy: never`
  and mounts source to `/project`.

### Requirement: Named volume for node_modules
The `app` service MUST use a named volume `npm_modules` for node_modules.

#### Scenario: Node modules preserved
- **WHEN** the container runs
- **THEN** `npm_modules` volume preserves linux-amd64 bindings and host darwin-arm64
  node_modules do NOT overwrite them.

### Requirement: run-loop-harness.sh bash 3.2 compatible
`scripts/run-loop-harness.sh` MUST NOT use bash 4+ features (`declare -A`, `[[ ]]`).

#### Scenario: No associative arrays
- **WHEN** the script is parsed for bash 4+ syntax
- **THEN** it uses flat string accumulation for key-value data.

#### Scenario: macOS date/stat fallbacks
- **WHEN** the script runs on macOS
- **THEN** it falls back to BSD `date`/`stat` syntax when GNU `gdate`/`gstat` are not available.

### Requirement: stop-containers excludes honcho
`make stop-containers` MUST NOT stop honcho containers.

#### Scenario: Honcho survives stop-containers
- **WHEN** `make stop-containers` runs while honcho is running
- **THEN** honcho containers (`honcho-api`, `honcho-database`, `honcho-redis`, `honcho-deriver`)
  remain running.

#### Scenario: Other compose projects stop
- **WHEN** `make stop-containers` runs
- **THEN** other compose projects (otu-*, docker-compose-files-*) are stopped.

### Requirement: nuke-all-containers script
`scripts/nuke-all-containers.sh` MUST stop/remove all containers, networks, volumes, and project images.

#### Scenario: Nuke stops and removes everything
- **WHEN** the script runs
- **THEN** it stops all containers, removes all non-default networks, removes all volumes,
  and removes project images (honcho*, otu*, docker-compose-files*, hello-world*).

#### Scenario: Timeout guards prevent hangs
- **WHEN** `nerdctl` is unresponsive
- **THEN** each call times out (default 10s, configurable via `N_TIMEOUT`) and returns 0.

#### Scenario: Platform-agnostic
- **WHEN** the script runs on Linux
- **THEN** it works the same (uses `nerdctl` from PATH, no macOS-specific code).

### Requirement: make nuke-containers target
The Makefile MUST provide `make nuke-containers` to run the nuke script.

#### Scenario: Nuke via make
- **WHEN** `make nuke-containers` runs
- **THEN** it executes `scripts/nuke-all-containers.sh` with optional `HONCHO_COMPOSE` env var.

### Requirement: Legacy nuke-all-containers target
The Makefile MUST provide `make nuke-all-containers` as a legacy alias.

#### Scenario: Legacy target works
- **WHEN** `make nuke-all-containers` runs
- **THEN** it runs the same nuke script.

## ADDED Acceptance Criteria

- `make build-app` succeeds via nerdctl compose on macOS.
- `make test-app` passes via nerdctl compose on macOS.
- `make stop-containers` excludes honcho containers.
- `make nuke-containers` runs to completion (no hangs).
- `make loop-harness` runs all stages (bash 3.2 compatible).
- `openspec validate macos-makefile-simplification` passes.
- `make check-docs-sync` passes (no drift).
