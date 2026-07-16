# secret-scan-show-findings Specification

## ADDED Requirements

### Requirement: secret-scan reports which file/rule fired
The `loop-secret-scan` loop-harness stage MUST print, on a detected secret, the
**file path, rule id, and line** of every finding (redacted), so the operator can
see exactly what was flagged — not just a generic "secrets detected" message.

#### Scenario: a secret is present in the working tree
- **WHEN** `make loop-secret-scan` runs and gitleaks finds a leak
- **THEN** the stage exits non-zero AND prints each finding as `file | rule | line`
  (read from the gitleaks JSON report)

#### Scenario: the working tree is clean
- **WHEN** `make loop-secret-scan` runs and gitleaks finds nothing
- **THEN** the stage prints `LOOP-SECRET-SCAN: clean.` and exits 0

### Requirement: working-tree scan is best-practice gitleaks
The scan MUST use gitleaks' **default ruleset** (`useDefault = true`) plus a tight
repo-local rule for low-entropy credential assignments (`repo-password-assignment`),
run with `detect --no-git` over the whole working tree (uncommitted files included),
containerized via `docker-compose-files/gitleaks.yaml`.

#### Scenario: a staged-but-uncommitted password file exists
- **WHEN** a file like `password.txt` containing `PASSWORD='...'` is staged (not committed)
- **THEN** `loop-secret-scan` catches it (the `repo-password-assignment` rule fires)

#### Scenario: legitimate non-secret assignments are not flagged
- **WHEN** the scan encounters `SECRET=${VAR}`, an empty `PASSWORD=`, or `API_KEY=os.getenv('X')`
- **THEN** no `repo-password-assignment` finding is raised (no false positives)
