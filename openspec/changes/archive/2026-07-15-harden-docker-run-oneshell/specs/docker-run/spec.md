## ADDED Requirements

### Requirement: docker_run continues subsequent recipe lines on success under .ONESHELL
The `docker_run` macro MUST NOT terminate the shared `.ONESHELL` recipe shell when the
wrapped container command succeeds. After a successful `docker_run`, the target's following
recipe lines MUST still execute.

#### Scenario: multi-line target runs all lines
- **WHEN** a target runs `$(call docker_run, <cmd>)` followed by additional recipe lines and `<cmd>` exits 0
- **THEN** every subsequent recipe line in that target executes and the target exits 0

#### Scenario: failure still propagates
- **WHEN** the wrapped container command exits non-zero
- **THEN** `docker_run` exits with that non-zero code and the target fails (fail-fast)

### Requirement: docker_run works in non-tty / piped / background contexts
`docker_run` MUST run the container command successfully when the make process's stdout is
not a TTY (piped, redirected, or background), providing a PTY via `script` because nerdctl
compose run hardcodes `--tty`.

#### Scenario: piped make run
- **WHEN** a `docker_run` target is run with stdout redirected to a file
- **THEN** the container command runs (no "provided file is not a console" error) and later recipe lines still execute

### Requirement: build-app and test-app run through docker_run
`build-app` and `test-app` MUST invoke the npm container via `docker_run` (not a raw
`docker compose run`), so under non-tty they actually build/test instead of silently
reporting success while the container fails with "provided file is not a console".

#### Scenario: build-app genuinely builds under non-tty
- **WHEN** `make build-app` (or `make loop-build-app`) runs with stdout piped
- **THEN** rollup runs and `dist/main.js` is created, with no "provided file is not a console" error

#### Scenario: test-app genuinely runs jest under non-tty
- **WHEN** `make test-app` (or `make loop-test-app`) runs with stdout piped
- **THEN** jest executes the plugin test suites and reports real pass/fail counts

### Requirement: RECORD_WORK_CMD resolves git and openspec
`RECORD_WORK_CMD` MUST set a PATH that resolves both `git` (at `/usr/bin/git`) and the
`openspec` CLI (at `/project/node_modules/.bin`) inside the container, so `record-work.py`
captures real git branch/commit metadata and openspec status without `git: not found`.

#### Scenario: record-work emits real metadata
- **WHEN** `make record-work CHANGE=<name>` runs
- **THEN** step 1 writes the prompt with no `git: not found`, step 2 drafts prose via host hermes, step 3 writes `agent-wiki/<date>-<name>.md`, and the target exits 0
