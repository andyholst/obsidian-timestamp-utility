## ADDED Requirements

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
