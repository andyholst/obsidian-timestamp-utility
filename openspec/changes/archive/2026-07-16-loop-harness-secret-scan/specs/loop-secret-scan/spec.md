# loop-secret-scan Specification

## ADDED Requirements

### Requirement: gitleaks secret scanning is a loop-harness stage
Secret scanning with gitleaks MUST be a first-class stage of the OpenSpec loop-harness
(`make loop-harness`), named `loop-secret-scan`. It MUST run gitleaks **inside a container**
via `docker-compose-files/gitleaks.yaml` (the `gitleaks` service built from
`containers/gitleaks/Dockerfile`), scanning the mounted repository. It MUST NOT invoke a local
Python wrapper (`scripts/secret_scanner.py`) and MUST NOT invoke a locally-installed gitleaks
binary from the Makefile — execution is docker compose only, consistent with the rest of the
harness (B9).

#### Scenario: loop-secret-scan runs containerized in the loop
- **WHEN** `make loop-secret-scan` runs (as a stage of `make loop-harness`)
- **THEN** gitleaks executes inside the `gitleaks` compose container against the mounted repo,
  and the Makefile target issues a `docker compose -f docker-compose-files/gitleaks.yaml run
  --rm gitleaks ...` command — never a `python3` or bare `gitleaks` invocation.

#### Scenario: a secret in the working tree fails the stage
- **WHEN** the repository contains a tracked secret and `make loop-secret-scan` runs
- **THEN** gitleaks exits non-zero, `make loop-secret-scan` fails (non-zero), and the loop is
  blocked (the stage is a mandatory gate, not a warning).

#### Scenario: a clean working tree passes the stage
- **WHEN** the repository has no secrets (per `.gitleaks.toml` allowlists)
- **THEN** gitleaks exits zero, `make loop-secret-scan` passes, and the loop continues.

### Requirement: no duplicate or python-backed secret-scan Makefile commands
The Makefile MUST NOT contain multiple targets that each independently run gitleaks, and MUST
NOT run gitleaks/secret-scanning through a Python interpreter in any target. There MUST be exactly
one canonical containerized secret-scan entry for the loop (`loop-secret-scan`), optionally plus
helper targets that build the image or run the pytest suite, but NO target that calls
`python3 scripts/secret_scanner.py` or a bare `gitleaks` binary. Hooks (`git-hooks/`) MAY still
reference `scripts/secret_scanner.py` for the local fail-closed developer guard, but the Makefile
loop path is container-only.

#### Scenario: single loop entry point
- **WHEN** the Makefile is inspected
- **THEN** there is exactly one target named `loop-secret-scan` that runs gitleaks, and no `check-secrets`
  / `scan-staged` / `scan-commit` / `make check` target that independently shells out to gitleaks
  or to `scripts/secret_scanner.py`.

#### Scenario: the loop target is container-only
- **WHEN** `make loop-secret-scan` is inspected
- **THEN** the recipe contains a `docker compose -f docker-compose-files/gitleaks.yaml` invocation
  and does NOT contain `python3` or `scripts/secret_scanner.py`.

### Requirement: gitleaks is wired into the B8 loop stage order
`loop-secret-scan` MUST be listed in the canonical loop stage chain (in `scripts/run-loop-harness.sh`
STAGES, the Makefile `loop-harness` comment, `AGENTS.md`, `hermes/skills/openspec-loop-harness.md`,
and `docs/openspec-engineering-loop-harness.md`) at a position that scans the working tree AFTER
code is generated/verified but before the final doc-sync gate — specifically as the stage
immediately BEFORE `check-docs-sync` (i.e. `... loop-build-app -> loop-test-app -> loop-secret-scan
-> check-docs-sync`). The B8 `check-docs-sync` gate MUST continue to pass after the stage is added.

#### Scenario: stage order includes loop-secret-scan
- **WHEN** the canonical stage chain is parsed from `scripts/run-loop-harness.sh`
- **THEN** `loop-secret-scan` appears between `loop-test-app` and `check-docs-sync`.

#### Scenario: B8 sync stays green
- **WHEN** `make check-docs-sync` runs after the stage is added
- **THEN** it PASSES (all sync docs agree on the updated stage order and B-range).
