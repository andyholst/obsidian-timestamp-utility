## ADDED Requirements

### Requirement: make changelog generates idempotently
`make changelog` MUST render the commits after the latest tag as a `## Unreleased` (or versioned)
section and OVERWRITE-merge it onto the curated history, producing NO duplicate `## ` headings on
re-run.

#### Scenario: First run with unreleased work
- **WHEN** there are commits ahead of the latest tag and `make changelog` runs
- **THEN** a single `## Unreleased` section appears at the top of CHANGELOG.md with the new commits
  regrouped by Conventional-Commit type.

#### Scenario: Re-run on the same tree
- **WHEN** `make changelog` runs again without new commits
- **THEN** the `## Unreleased` heading count stays constant (no duplicate `## Unreleased` headings).

### Requirement: make bump-from-changelog is stable and never climbs
`make bump-from-changelog` MUST derive `<next>` from the RELEASED state only (highest git tag merged
into `origin/main` + 1 patch), re-label `## Unreleased` -> `## <next>`, and bump `package.json`,
`manifest.json`, the TS test file `version:` literal, and `versions.json`.

#### Scenario: Re-run does not climb or pile up tags
- **WHEN** `make bump-from-changelog` runs three times on the same branch
- **THEN** the version stays at the same `<next>` each time, exactly ONE local `v<next>` tag exists,
  and `package.json`/`manifest.json`/`src/__tests__/main.test.ts` all read `<next>`.

#### Scenario: versions.json uses the real minAppVersion
- **WHEN** `make bump-from-changelog` bumps to `<next>`
- **THEN** `versions.json` gains `<next>` mapped to `manifest.json` `minAppVersion` (NOT a hardcoded
  constant), gap versions are filled, and the map stays semver-sorted + contiguous.

### Requirement: bump keeps the TS test file version in lock-step
`make bump-from-changelog` MUST update the `version:` literal inside `src/__tests__/main.test.ts`
(and `src/main.ts` if present) to `<next>` so the test mock matches the released plugin version.

#### Scenario: TS test mock version bumped
- **WHEN** `make bump-from-changelog` runs and the test mock currently reads an older version
- **THEN** `src/__tests__/main.test.ts` `version: '<next>'` matches `package.json` `version`.

### Requirement: corner cases are handled safely
`make bump-from-changelog` MUST fail-closed only when `<next>` is already released on the REMOTE, and
MUST be a no-op (not error) when there is no unreleased work.

#### Scenario: already released on remote
- **WHEN** `v<next>` already exists on `origin`
- **THEN** the command exits non-zero with a REFUSING message and changes nothing locally.

#### Scenario: no unreleased work
- **WHEN** the changelog top section is already a released/curated `## <version>` (not `## Unreleased`)
- **THEN** the command does NOT relabel it and exits cleanly (idempotent no-op).

### Requirement: make squash-commits produces one typed commit
`make squash-commits` MUST squash the staged/branch commits into ONE Conventional-commit with a
valid `type(scope):` prefix, gated by commitlint.

#### Scenario: squash with mixed commits
- **WHEN** the branch has several feat/fix commits and `make squash-commits` runs
- **THEN** history collapses to a single commit whose message starts with a valid Conventional type
  and `git log --oneline` shows exactly one new commit over the base.
