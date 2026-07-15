## ADDED Requirements

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
