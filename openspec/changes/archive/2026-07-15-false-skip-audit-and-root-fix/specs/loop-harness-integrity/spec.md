# loop-harness-integrity Specification

## ADDED Requirements

### Requirement: Skip conditions must be truthful (no false skips)
The agentic test suite MUST NOT skip a test when its required dependency is actually present in the
execution environment. A skip whose condition is false (the dependency IS reachable) is a **false
skip** and MUST be fixed, because it lets `make loop-harness` report green while real coverage is
silently lost.

#### Scenario: integration container mounts repo root at /app and /project
- **WHEN** a test resolves the repo root inside the integration container
- **THEN** it MUST prefer the unshadowed mount (`/project`, which contains `src/main.ts`) over the
  shadowed `/app/src` (Python agentics source), so `src/main.ts` and `src/__tests__/main.test.ts`
  are found and the test RUNS instead of skipping.

#### Scenario: TS test scaffold is reachable
- **WHEN** `plugin_ts_tests_present(project_root)` is evaluated after the repo root is resolved to
  the unshadowed mount
- **THEN** it MUST return True for a seeded temp dir that copied the real `src/` (so jest-dependent
  pipeline tests RUN, not skip).

### Requirement: docker_run must pass test filters intact
The `docker_run` Makefile helper MUST deliver the full `TEST_FILTER`/`INTEGRATION_TEST_FILTER`
string (including quoted tokens like `TEST_FILTER='-m e2e'`) to the container unaltered. Splitting
the filter into separate shell tokens MUST NOT happen.

#### Scenario: make test-agents-e2e runs
- **WHEN** `make test-agents-e2e` (default `INTEGRATION_TEST_FILTER=-m e2e`) is invoked
- **THEN** the filter reaches pytest intact and the e2e suite executes (exit 0), NOT `Error 127`
  from a mangled command.

### Requirement: Backup tests skip only on a real impossibility
`test_backup_feature.py` MUST skip only when the backup directory genuinely cannot be created
(e.g. unwritable `PROJECT_ROOT`); it MUST NOT skip on a stale "Dagger container limitation" reason,
because this repo uses docker compose, not Dagger.

#### Scenario: backup dir creatable in container
- **WHEN** `_backup_project_files(PROJECT_ROOT)` is called with a writable repo root
- **THEN** `BACKUP_DIR` is created and the backup assertions RUN (not skip).
