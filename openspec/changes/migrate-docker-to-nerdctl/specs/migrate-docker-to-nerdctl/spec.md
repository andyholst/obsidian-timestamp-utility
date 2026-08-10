# Spec: Migrate from Docker to nerdctl

## ADDED Requirements

### Requirement: All container operations use nerdctl compose exclusively
The system MUST use `nerdctl compose` for all container orchestration. No `docker compose`, `docker build`, or `docker run` commands may appear in the Makefile, shell scripts, CI workflows, or any project-internal tooling. The `docker` binary may remain on the host as a fallback but must never be invoked by project tooling.

#### Scenario: Makefile uses nerdctl compose
- **WHEN** a developer runs `make build-app`, `make test-app`, `make loop-harness`, or any other container-invoking target
- **THEN** the command executed is `nerdctl compose -f <compose-file> run --rm ...` (or `nerdctl build`)

#### Scenario: Shell scripts use nerdctl compose
- **WHEN** a shell script in `scripts/` invokes a container runtime
- **THEN** it uses `nerdctl compose` or `nerdctl` commands, never `docker`

#### Scenario: CI workflows use nerdctl
- **WHEN** GitHub Actions workflows run containerized steps
- **THEN** they use `nerdctl` or `nerdctl compose` (or Docker's official action which handles the runtime transparently)

### Requirement: Containerfiles replace Dockerfiles
All container build definitions MUST be named `Containerfile` instead of `Dockerfile`, following nerdctl's naming convention. The file contents remain compatible — nerdctl reads both formats identically.

#### Scenario: All containers use Containerfile
- **WHEN** a container needs to be built (agents, npm, pip, gitleaks, gitleaks-tests)
- **THEN** the build definition is at `containers/<name>/Containerfile`, not `Dockerfile`

### Requirement: Compose files are compatible with nerdctl compose
All docker-compose YAML files MUST be compatible with `nerdctl compose`. Docker-specific extensions (like `buildx` directives or Docker Desktop-specific features) must be removed or replaced.

#### Scenario: Compose files work with nerdctl
- **WHEN** `nerdctl compose -f <file> up` is run
- **THEN** all services start and function correctly without errors

### Requirement: Documentation reflects nerdctl usage
All documentation, comments, and user-facing text MUST reference `nerdctl` instead of `docker` when describing container operations.

#### Scenario: Documentation references nerdctl
- **WHEN** a developer reads AGENTS.md, the loop harness docs, or the Hermes skill
- **THEN** they see `nerdctl` / `nerdctl compose` references, not `docker`

### Requirement: PTY runner remains functional with nerdctl
The `scripts/pty_runner.py` script MUST continue to work correctly with `nerdctl compose run`, which still requires a real PTY (it hardcodes `--interactive --tty`).

#### Scenario: PTY runner works with nerdctl
- **WHEN** the Makefile's `docker_run` macro wraps a command in `pty_runner.py` for non-TTY output
- **THEN** the container runs successfully and output is captured

### Requirement: Stop-containers target uses nerdctl
The `stop-containers` Makefile target MUST use `nerdctl ps` and `nerdctl stop` to manage containers.

#### Scenario: Containers are stopped cleanly
- **WHEN** `make stop-containers` is run
- **THEN** all compose project containers are stopped using `nerdctl` commands
