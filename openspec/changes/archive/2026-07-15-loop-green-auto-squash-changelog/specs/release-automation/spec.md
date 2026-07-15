## ADDED Requirements

### Requirement: engineering-done archives all changes before finalisation
The system MUST, when the harness + loop engineering is done (every active OpenSpec change has all
tasks ticked, open=0), archive EVERY active change BEFORE squashing/changelog/bump — gated on a clear
backlog. If any active change still has an open task, finalisation MUST refuse.

#### Scenario: dirty backlog refuses
- **WHEN** any active change under `openspec/changes/` has an open `- [ ]` task
- **THEN** `make assert-backlog-clear` (and therefore `make loop-finish`) exits non-zero and archives
  nothing, squashes nothing, bumps nothing

#### Scenario: clear backlog archives all then finalises
- **WHEN** every active change has open=0
- **THEN** `make archive-all-complete` archives each via `phase7-archive`, then `loop-finish`
  proceeds to squash -> changelog -> bump-from-changelog -> changelog-format

### Requirement: loop-green finalises with squash + changelog + bump
The system MUST, when the loop-harness gate is green, finalise staged work by squashing, regenerating
the changelog (complete + clean), and bumping the version — in that order.

#### Scenario: green gate triggers finalisation
- **WHEN** the loop-harness reports all 7 gates green (loop-collect, loop-unit, loop-unit-real,
  loop-e2e, loop-integration, loop-build-app, loop-test-app)
- **THEN** `make loop-finish` (or `make release-flow`) runs `squash-commits` -> `changelog` ->
  `bump-from-changelog` -> `changelog-format` in order

#### Scenario: red gate must NOT finalise
- **WHEN** any loop gate is red
- **THEN** `loop-finish` refuses (non-zero) and performs NO squash, NO changelog write, NO bump

### Requirement: squash result is a single typed commit
The system MUST squash the staged work into exactly one Conventional-Commit-typed, commitlint-passed
commit (the existing `squash-commits` behaviour), and MUST NOT push (B14).

#### Scenario: typed + commitlint-gated squash
- **WHEN** `squash-commits` runs
- **THEN** one commit is created with a valid `type(scope):` first line, validated by commitlint

### Requirement: changelog is complete and clean after finalisation
The regenerated changelog MUST contain every commit captured by the squash (nothing omitted) and MUST
be markdown-formatted (no stray blank lines, trimmed whitespace).

#### Scenario: nothing omitted
- **WHEN** the changelog is regenerated after the squash
- **THEN** the squashed commit's subject + body appear in the new version section

#### Scenario: linted/formatted
- **WHEN** finalisation completes
- **THEN** `CHANGELOG.md` passes `make changelog-format` (idempotent, no trailing whitespace, single
  blank line between bullets)

### Requirement: harness/loop-agent skill documents the green-end behaviour
The OpenSpec loop-harness skill (and AGENTS.md) MUST state that a GREEN loop ends with squash +
changelog + bump, gated on green, never on red, and that the changelog must be complete and formatted.

#### Scenario: skill/AGENTS.md in agreement
- **WHEN** the change is archived
- **THEN** `hermes/skills/openspec-loop-harness.md` and `AGENTS.md` both describe the green-end
  squash+changelog+bump sequence (B8 sync)
