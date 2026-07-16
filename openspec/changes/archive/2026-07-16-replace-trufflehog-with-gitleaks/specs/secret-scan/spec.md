# secret-scan Specification

## ADDED Requirements

### Requirement: Replace the broken TruffleHog Action with gitleaks
The system MUST NOT use the `trufflesecurity/trufflehog` GitHub Action for secret
scanning. The broken `trufflehog.yml` workflow MUST be replaced by a gitleaks-based
workflow (using `gitleaks/gitleaks-action@v2`) that scans every push and pull request
without relying on unsupported action inputs or a same-base/head abort.

#### Scenario: No TruffleHog usage remains
- **WHEN** the repository is inspected
- **THEN** no workflow references `trufflesecurity/trufflehog`, and
  `.github/workflows/trufflehog.yml` is a gitleaks workflow (`gitleaks/gitleaks-action@v2`,
  `fetch-depth: 0`, `GITLEAKS_CONFIG=.gitleaks.toml`).

#### Scenario: The gitleaks workflow scans correctly on a normal push
- **WHEN** a push occurs to any branch
- **THEN** the `trufflehog.yml` (gitleaks) workflow runs gitleaks `detect` with `fetch-depth: 0`
  and exits non-zero (failing the run) only when a real secret is found, never due
  to invalid inputs or a BASE==HEAD abort.

### Requirement: Pre-commit hook blocks secrets in staged content
`git-hooks/pre-commit` MUST, before allowing a commit, scan the staged (index)
content for secrets using the secret scanner engine. If any secret is detected, the
hook MUST exit non-zero (rejecting the commit) and print the offending finding(s).
If no secret is detected, the hook MUST exit zero and not block the commit.

#### Scenario: A staged file contains a real secret
- **WHEN** a developer stages a file containing an AWS secret access key (or other
  detected secret) and runs `git commit`
- **THEN** the pre-commit hook exits non-zero, prints the secret finding (with file
  and a redacted/truncated hint), and the commit is NOT created.

#### Scenario: Staged content is clean
- **WHEN** a developer stages ordinary source files with no secrets and runs
  `git commit`
- **THEN** the secret scan reports no findings, the hook exits zero, and the commit
  succeeds.

#### Scenario: A staged file contains only a false-positive-safe token
- **WHEN** a staged file contains a value that matches a secret pattern but is on
  the gitleaks `allowlist` / a documented test fixture
- **THEN** the scanner reports no finding for that token and the commit succeeds.

### Requirement: commit-msg hook blocks secrets in the commit message
`git-hooks/commit-msg` MUST scan the commit message (read from the message file
passed as `$1`) for secrets using the secret scanner engine. If a secret is
detected, the hook MUST exit non-zero and print the finding; otherwise it MUST exit
zero. The existing Conventional-Commit lint (commitlint) MUST continue to run as
before.

#### Scenario: The commit message contains a secret
- **WHEN** a developer runs `git commit -m "fix: rotate key AKIA...EXAMPLE"`
- **THEN** the commit-msg hook exits non-zero and rejects the commit with the secret
  finding, in addition to any commitlint check.

#### Scenario: The commit message is clean
- **WHEN** a developer runs `git commit -m "feat(scanner): add gitleaks hook"`
- **THEN** the secret scan reports no findings, commitlint runs, and the commit
  proceeds (subject to the existing Conventional-Commit rule).

### Requirement: A Python secret-scanner engine that delegates 100% to gitleaks
The system MUST provide a Python module `scripts/secret_scanner.py` exposing a
testable API: `scan_staged_content()`, `scan_commit_message(text)`, `scan_file(path)`,
`scan_text(text)`, and `scan_repo()`. The engine MUST delegate ALL detection to gitleaks
— there is NO homemade regex/entropy detector. It MUST prefer running gitleaks inside a
container image (nerdctl/docker, when a runtime is present) and fall back to a local
`gitleaks` binary (`GITLEAKS_BIN`); `GITLEAKS_RUNTIME=none|false|0` forces binary mode.

#### Scenario: gitleaks is available (binary)
- **WHEN** a `gitleaks` binary is on `PATH` (or `GITLEAKS_BIN` set) and `scan_text` is called
  with secret-bearing text
- **THEN** the engine delegates to `gitleaks` and returns a non-clean `ScanResult` whose
  findings include the secret (rule id, redacted match, file, line).

#### Scenario: gitleaks container runtime is available
- **WHEN** a container runtime (nerdctl/docker) is present and `scan_repo` / `scan_staged_content`
  runs
- **THEN** the engine runs gitleaks inside the `containers/gitleaks` image against the mounted
  repo and returns the same structured findings.

#### Scenario: gitleaks is absent
- **WHEN** no container runtime and no gitleaks binary are available
- **THEN** the engine returns a non-clean `ScanResult` with engine `"unavailable"` and a clear
  message, refusing to silently pass (fail-closed).

#### Scenario: Clean text
- **WHEN** `scan_text` is called with ordinary text
- **THEN** the engine returns a clean `ScanResult` (no findings).

### Requirement: Tests cover happy, negative, and integration paths with the real gitleaks binary
The system MUST provide `tests/test_secret_scanner.py` (hermetic unit tests, mocking only
subprocess/paths) and `tests/test_secret_scanner_integration.py` (no-mock integration tests that
write real example files at runtime and assert actual gitleaks rule output — e.g. a slack token is
detected, an AWS documented example key is allowlisted, clean input passes, staged blobs and commit
messages are scanned, and the CLI exits non-zero on a secret / zero when clean). All tests MUST pass
under `python -m pytest tests/test_secret_scanner.py tests/test_secret_scanner_integration.py`, and
the integration suite MUST skip cleanly (not error) when no gitleaks binary is present.

#### Scenario: Negative tests detect real secrets
- **WHEN** `tests/test_secret_scanner_integration.py` runs against secret-bearing inputs
- **THEN** the corresponding assertions confirm a non-clean result and the specific rule is reported.

#### Scenario: Happy tests pass clean input
- **WHEN** the suites run against clean inputs
- **THEN** the corresponding assertions confirm a clean result with no findings; a clean repo
  (`make check-secrets`) reports no secrets.
