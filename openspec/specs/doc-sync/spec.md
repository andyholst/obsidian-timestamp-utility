# doc-sync Specification

## Purpose
TBD - created by archiving change doc-sync-tests. Update Purpose after archive.
## Requirements
### Requirement: doc-sync gate has hermetic behavioural tests
The doc-sync gate (`scripts/check-docs-sync.py`) MUST have a hermetic pytest suite that
asserts its PASS/FAIL semantics against fixture copies of the B8 sync files, so a
regression in the gate (e.g. a normalization bug that hides a B-range drift) is caught.

#### Scenario: aligned fixtures pass
- **WHEN** the test suite runs `check_docs_sync()` against a fixture set where every sync
  file is correctly aligned (canonical stage order incl. `loop-ts-floor`, `loop-ts-floor`
  token, and B-range `>= B25`) — including glyph variants (`->`, `→`, en-dash `B1-B25`)
- **THEN** the suite asserts the gate returns no drift and exit code 0.

#### Scenario: missing loop-ts-floor in a file's chain fails
- **WHEN** the Makefile fixture drops `loop-ts-floor` from its canonical stage-order chain
- **THEN** the suite asserts the gate reports a drift in `Makefile` (stage order), exit 1.

#### Scenario: low B-range in a file fails
- **WHEN** the AGENTS.md fixture declares `B1-B21` instead of `B1-B25`
- **THEN** the suite asserts the gate reports a drift in `AGENTS.md` (B-behaviour range),
  exit 1.

#### Scenario: reordering a secondary chain mention is not a false positive
- **WHEN** a fixture reorders a non-canonical (secondary) mention of the stage chain while
  the canonical contiguous chain is still present elsewhere in the same file
- **THEN** the suite asserts the gate returns no drift (exit 0) — the gate does not
  over-flag.

#### Scenario: exactly the offending file is reported
- **WHEN** only one sync file in a fixture set is misaligned
- **THEN** the suite asserts the gate reports exactly that file, and no other file.

### Requirement: gate unit tests run at the start of loop-harness
`make loop-harness` (via `scripts/run-loop-harness.sh`) MUST run the doc-sync gate's unit
tests and the live `check-docs-sync` gate as the FIRST pre-flight step (PRE-FLIGHT 0),
before any of the eight loop stages, so a broken gate or a drifted doc fails the run early.

#### Scenario: pre-flight runs first and fails fast
- **WHEN** `make loop-harness` starts
- **THEN** `make test-check-docs-sync` and `make check-docs-sync` execute before
  `loop-collect`, and a non-zero result aborts the run with a clear pre-flight failure.

### Requirement: B8 doc-sync gate
The build MUST provide a deterministic checker that verifies the four (actually five) B8 docs
agree on the loop-harness stage order, the `loop-ts-floor` guard, and the B-behaviour range, and
MUST fail (non-zero exit) when any of them drift.

#### Scenario: all sync files agree
- **WHEN** `make check-docs-sync` runs with every B8 doc containing the canonical stage-order
  string, the `loop-ts-floor` stage, and the same B-behaviour range
- **THEN** the command exits 0 and prints `DOC-SYNC: PASS`.

#### Scenario: a doc drifts
- **WHEN** `make check-docs-sync` runs and any B8 doc is missing the canonical stage-order string
  or the `loop-ts-floor` reference or disagrees on the B-behaviour range
- **THEN** the command exits non-zero, prints each offending file, and reports which token drifted.

### Requirement: Hermes drift report
The checker MUST, on drift, invoke the project-manager Hermes CLI (`hermes -z`, profile
`project-manager`) with a prompt describing the exact drift, scoped to the current working
directory, so the human gets an actionable natural-language explanation of what to fix.

#### Scenario: Hermes prompt fires on drift
- **WHEN** a drift is detected
- **THEN** the checker calls `hermes profile use project-manager` then `hermes -z "<drift prompt>"`
  with `cwd` set to the current working directory, and continues to exit non-zero even if Hermes
  is unavailable.

#### Scenario: Hermes scoping to current path
- **WHEN** the checker is invoked from any directory inside the repo
- **THEN** the `cwd` passed to `hermes -z` is that directory (the path where the command is asked),
  not a hardcoded root.

### Requirement: gate wired into the loop
The doc-sync check MUST run as part of the hermetic loop pre-flight so drift cannot pass silently.

#### Scenario: wired into loop-collect
- **WHEN** `make loop-collect` (or `make loop-harness`) runs
- **THEN** `check-docs-sync` executes as a hermetic sub-step and a non-zero result fails the stage.

