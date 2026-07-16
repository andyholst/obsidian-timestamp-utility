# secret-scanner-loop-tests Specification

## ADDED Requirements

### Requirement: secret-scanner test suite is a loop-harness stage
The secret-scanner's own pytest suite (`tests/test_secret_scanner.py` + `tests/
test_secret_scanner_integration.py`) MUST run as a **loop-harness stage**
(`loop-secret-scan-tests`), so the scanner's detection logic is verified on every
loop run — not just the repo scan.

#### Scenario: the loop runs the secret-scanner tests
- **WHEN** `make loop-harness` (or `scripts/run-loop-harness.sh`) executes
- **THEN** the stage `loop-secret-scan-tests` runs the secret-scanner pytest suite
  inside the `gitleaks-tests` compose container (docker compose only, B9) and
  FAILS the loop if any test is red.

#### Scenario: the suite is hermetic enough to run in the loop
- **WHEN** `loop-secret-scan-tests` runs
- **THEN** it uses the REAL gitleaks binary (containerized, no mocks on detection),
  builds from `containers/gitleaks-tests/Dockerfile`, and exits non-zero on failure
  (fail-closed, like every other loop gate).

### Requirement: the actual secret scan lives in the hook + CI, NOT the loop
The gitleaks **repo scan** MUST NOT be a loop-harness stage. It runs in the
pre-commit hook (`scripts/secret_scanner.py --staged`), the commit-msg hook
(`--message-file`), and CI (`.github/workflows/trufflehog.yml`). A standalone
`make loop-secret-scan` target exists only for on-demand scans.

#### Scenario: scan does not re-run in the loop
- **WHEN** the loop-harness stage chain is evaluated
- **THEN** `loop-secret-scan` is NOT in the chain (the hook already guards every
  commit); only `loop-secret-scan-tests` is present.

### Requirement: no duplicate secret-scanner test entry
The secret-scanner tests MUST have exactly ONE canonical loop entry
(`loop-secret-scan-tests`); `test-secret-scanner` stays a host-side convenience
helper and MUST NOT independently invoke gitleaks through Python.

#### Scenario: stage ordering
- **WHEN** the canonical stage order is evaluated
- **THEN** `loop-secret-scan-tests` follows `loop-test-app` and precedes
  `check-docs-sync` in the B8 sync docs (AGENTS.md, skill, docs).
