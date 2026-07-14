# openspec-scaffold Specification

## ADDED Requirements

### Requirement: Change directory created via the openspec CLI
The harness MUST create an OpenSpec change directory by invoking the real `openspec` CLI
(`openspec new change <NAME> [--description <DESC> --goal <GOAL>]`) — it MUST NOT hand-write
the directory shape with raw file writes (per durable behaviour B15). The generated directory
MUST contain the CLI-produced `.openspec.yaml` and `README.md`.

#### Scenario: new change created
- **WHEN** `make openspec-new NAME=<name>` (or `scripts/scaffold-openspec-change.sh --name <name>`) runs
- **THEN** it calls `openspec new change <name>` (verified: the change dir exists and contains
  `.openspec.yaml` written by the CLI, not by the script), and it exits non-zero if the CLI step fails.

#### Scenario: name already exists
- **WHEN** the target runs for a `<name>` whose `openspec/changes/<name>` already exists
- **THEN** the script detects this (either the CLI refuses, or the script pre-checks) and exits
  non-zero with a clear message, never silently overwriting an existing change.

### Requirement: Conventional files seeded from a template
After the CLI creates the directory, the harness MUST seed `proposal.md`, `tasks.md`, and
`specs/<CAPABILITY>/spec.md` from a single heredoc template populated with the caller's
`NAME` / `DESC` / `GOAL` / `CAPABILITY` arguments, so every new change has the same validated
shape. The `spec.md` MUST use the OpenSpec delta format (`## ADDED Requirements` →
`### Requirement:` → `#### Scenario:` with `WHEN`/`THEN`).

#### Scenario: seeded files present and valid
- **WHEN** the harness finishes for a new change `<name>` with capability `<cap>`
- **THEN** `openspec/changes/<name>/proposal.md`, `tasks.md`, and `specs/<cap>/spec.md` exist,
  `tasks.md` is in checkbox form, and `openspec validate <name>` exits 0.

### Requirement: Makefile target wraps the script with required NAME
The Makefile MUST provide an `openspec-new` target that invokes the script with `NAME`
(required), and optional `DESC` / `GOAL` / `CAPABILITY` (defaulting `CAPABILITY` to `NAME`),
with `b9-perms` as a prerequisite. It MUST refuse to run when `NAME` is empty.

#### Scenario: invoked with a name
- **WHEN** `make openspec-new NAME=my-change DESC="..." GOAL="..." CAPABILITY=my-cap` runs
- **THEN** it applies the B9 permission floor, then invokes the script with those args, and
  exits non-zero if the script fails.

#### Scenario: invoked without a name
- **WHEN** `make openspec-new` runs with no `NAME`
- **THEN** it prints an error telling the caller to set `NAME=<name>` and exits non-zero, writing
  no change.

### Requirement: B8 documentation of the harness
AGENTS.md Phase 2 and the `openspec-loop-harness` skill MUST both reference `make openspec-new`
as the canonical way to create a change in this repo, so the four harness artifacts agree. No
git commit/push is performed by the target (B4/B14).

#### Scenario: documentation agrees
- **WHEN** a reviewer reads AGENTS.md Phase 2 and `hermes/skills/openspec-loop-harness.md`
- **THEN** both point change creation at `make openspec-new NAME=<name>` (or the underlying
  script), and neither describes a hand-authored change directory as the standard path.
