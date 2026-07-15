# release-automation Specification

## ADDED Requirements

### Requirement: Changelog Unreleased section derived from commit types
The `make changelog` command MUST regenerate the `## Unreleased` section of `CHANGELOG.md`
from the commits in `<latest-released-tag>..HEAD`, grouping each commit under a section
heading determined by its Conventional-Commit type.

#### Scenario: feat commit appears under New Features
- **WHEN** `make changelog` runs and `git log <latest-tag>..HEAD` contains a commit whose
  subject matches `^feat(\(...\))?:\s*...`
- **THEN** `CHANGELOG.md`'s `## Unreleased` contains a `### ✨ New Features` section listing
  that commit (as `- **<subject>**`).

#### Scenario: fix commit appears under Bug Fixes
- **WHEN** a commit in the unreleased range has a `fix(...):` subject
- **THEN** it appears under `### 🐞 Bug Fixes`.

#### Scenario: chore commit appears under Maintenance
- **WHEN** a commit in the unreleased range has a `chore(...):` subject
- **THEN** it appears under `### 🛠️ Maintenance`.

#### Scenario: aligns with the squashed commit
- **WHEN** the unreleased range is a single squashed commit (e.g. `feat(release): ...`)
- **THEN** the `## Unreleased` section reflects exactly that squashed message, grouped by its
  type, and excludes off-branch / leaked probe commits.

#### Scenario: idempotent re-run
- **WHEN** `make changelog` is run a second time
- **THEN** the `## Unreleased` section is overwritten in place (no duplicate `## Unreleased`
  heading, no duplicate group sections, no drift in content).

#### Scenario: commit body is sectionized under the same type
- **WHEN** a commit in the unreleased range has a multi-line body
- **THEN** the body lines are rendered as indented sub-bullets under the SAME type section as
  its subject (e.g. a `fix:` commit's body bullet appears under `### 🐞 Bug Fixes`), so the
  body content is sectionized "right as the others".

#### Scenario: idempotent across repeated runs
- **WHEN** `make changelog` is run multiple times (with or without restoring the baseline first)
- **THEN** the `## Unreleased` section is byte-identical each run (no duplicate `## Unreleased`
  heading, no duplicate group sections, no duplicated body bullets).
