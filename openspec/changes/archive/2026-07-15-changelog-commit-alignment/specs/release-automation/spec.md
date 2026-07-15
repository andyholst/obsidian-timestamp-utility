## ADDED Requirements

### Requirement: changelog reflects the squashed commit graph
`make changelog` MUST regenerate `## Unreleased` from the **current commit graph** (after
`make squash-commits`), so its bullets correspond to the squashed commit(s) between the base and
HEAD, grouped by Conventional-Commit type.

#### Scenario: after squash, changelog matches git log
- **WHEN** the branch has been squashed to one commit `b81bf66` and `make changelog` runs
- **THEN** the `## Unreleased` section's bullets are derived from `git log <base>..HEAD` (the
  squashed commit), grouped by type (✨/🐞/📝/🛠️), with no raw `feat: ...` subject lines.

### Requirement: leak-free changelog
`make changelog` MUST NOT persist leaked test/probe commits (`feat(proof)`, `feat: test`,
`feat: wipå`, bare `feat: ...`) into the curated `CHANGELOG.md`.

#### Scenario: scrub existing garbage
- **WHEN** `CHANGELOG.md` contains leaked test commits from prior probe runs
- **THEN** `make changelog` drops them and the surviving `## Unreleased` reflects only real,
  squashed work.

### Requirement: alignment is verifiable
The top `## Unreleased` bullets MUST be derivable from `git log <base>..HEAD`, proving the
changelog and commit graph agree.

#### Scenario: idempotent alignment
- **WHEN** `make changelog` runs twice on the same squashed tree
- **THEN** the `## Unreleased` heading count stays constant and the bullets stay aligned with
  `git log <base>..HEAD` (no duplicate headings, no drift).
