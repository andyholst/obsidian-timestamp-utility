# release-automation Specification

## ADDED Requirements

### Requirement: Backlog-clear gate before finalisation
The `make assert-backlog-clear` target MUST FAIL (non-zero exit) if any active OpenSpec change
under `openspec/changes/` still contains an open `- [ ]` task, and MUST print
`OK: no active change has open tasks.` only when every active change has open=0.

#### Scenario: open task present
- **WHEN** an active change has at least one `- [ ]` task
- **THEN** `make assert-backlog-clear` exits non-zero and lists the offending change(s).

#### Scenario: backlog clear
- **WHEN** every active change has open=0
- **THEN** `make assert-backlog-clear` prints the OK line and exits 0.

### Requirement: Archive-all active changes
The `make archive-all-complete` target MUST archive every active OpenSpec change (via
`phase7-archive`, which enforces the B16 open-task gate per change), and MUST depend on
`assert-backlog-clear`.

#### Scenario: archive all
- **WHEN** `make archive-all-complete` runs with a clear backlog
- **THEN** each active change is archived (spec merged) and none remain active.

### Requirement: Green-gated loop finalisation
The `make loop-finish` target MUST, after the backlog is clear and all changes archived, chain
`squash-commits` → `changelog` → `bump-from-changelog` → `changelog-format`, and MUST NOT push
(B4/B14).

#### Scenario: loop-finish sequence
- **WHEN** `make loop-finish` runs (loop gate green per B20, backlog clear)
- **THEN** it produces one TYPED squashed commit + a regenerated CHANGELOG (## Unreleased →
  ## <next>) + bumped package/manifest/versions.json, and exits 0 with no push.
