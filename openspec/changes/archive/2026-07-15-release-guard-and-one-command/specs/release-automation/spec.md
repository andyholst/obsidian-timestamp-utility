# release-automation Specification

## MODIFIED Requirements

### Requirement: Plugin version bumps the Obsidian way
The repository MUST provide a `bump-version` Makefile target that increments the plugin version
using the Obsidian convention: it updates `package.json` `version`, `manifest.json` `version`, and
appends `{"<new-version>": "<minAppVersion>"}` to `versions.json` (preserving existing entries).
Default bump is patch; `PART=minor`/`PART=major` override. The new version MUST equal the
`node -p "require('./package.json').version"` value the `TAG` Makefile variable already derives.

#### Scenario: patch bump updates all three version files
- **WHEN** `make bump-version` runs on version `0.4.10`
- **THEN** `package.json` and `manifest.json` `version` become `0.4.11`, and `versions.json`
  contains a `"0.4.11": "0.15.0"` entry (with prior entries intact).

#### Scenario: minor/major override
- **WHEN** `make bump-version PART=minor` runs on `0.4.10`
- **THEN** the version becomes `0.5.0` across all three files.

### Requirement: CHANGELOG regenerates on release
The release flow MUST regenerate `CHANGELOG.md` (reusing the existing `changelog` target via
`git_chglog`) so it reflects the squashed commit history, SECTIONED by commit type.

#### Scenario: changelog regenerated
- **WHEN** the release flow runs
- **THEN** `CHANGELOG.md` is (re)written and contains the new release entry, categorized by type.

### Requirement: Commits squash and release is tagged locally (no push)
After the bump, the flow MUST run `squash-commits` (typed, fail-closed) and then create a LOCAL git
tag `v<version>`. Tagging MUST be local only — no `git push` (B14). Pushing remains a deliberate
human action.

#### Scenario: squash then local tag
- **WHEN** the release flow completes
- **THEN** there is exactly one squashed commit for the change and a local `v<version>` tag exists,
  and no push was performed.

### Requirement: Release change does not regress the agentic suite
This change adds Makefile mechanics only. It MUST NOT alter the deterministic floor or the 7
verification stages, and the hermetic agentic gates MUST remain green.

#### Scenario: hermetic gates still pass
- **WHEN** `make loop-collect` and `make loop-unit` run after the change
- **THEN** they pass (no agent Python source changed).

## ADDED Requirements

### Requirement: Local-only bump + tag without the full release flow
The repository MUST provide a `bump-local` Makefile target that runs `check-released` →
`bump-version` (Obsidian way) → `tag-release`. It MUST NOT run `squash-commits`, `changelog`, or
`release-notes`. It advances the version and creates a LOCAL tag only — for staging the version
locally before the publish (`release`) step. NO push (B14).

#### Scenario: bump-local advances version + local tag, no squash/changelog
- **WHEN** `make bump-local PART=patch` runs on an unreleased current version
- **THEN** `package.json`/`manifest.json`/`versions.json` advance one patch, a local `v<new>` tag is
  created, and NO squashed commit / CHANGELOG regeneration occurred.

### Requirement: Local release prep is a single easy Make command; GitHub release is CI-driven
The repository MUST provide a `release-prep` Makefile target that runs `check-released` → `bump-version`
→ `squash-commits` (typed, fail-closed) → `changelog` (regenerate CHANGELOG.md) → `release-notes`
(refresh the README release-notes block) → `tag-release` (LOCAL tag only). It MUST NOT push. The
actual GitHub release is cut by CI (`.github/workflows/release.yml`) on merge to `main` / tag push.
The pre-existing `release` (zip) target used by that workflow MUST remain intact and MUST NOT be overridden.

#### Scenario: one command bumps, squashes, changelogs, notes, and tags locally
- **WHEN** `make release-prep PART=patch` runs with the current version not yet released and a forward gap
- **THEN** the version is bumped the Obsidian way, one typed commit is squashed, CHANGELOG.md is
  regenerated (sectioned), the README release-notes block is refreshed, and a local `v<new>` tag is created (no push).

### Requirement: Never bump a version already released on GitHub (and require a forward gap)
Before bumping, `check-released` MUST check whether the CURRENT `package.json` version is already
released on the GitHub project repo (a remote git tag equal to the version OR `v<version>`,
tolerant of both forms) OR does NOT advance past the latest released version (no semver gap). If
either holds, the bump MUST FAIL (non-zero) with a clear message and MUST NOT bump, squash, or tag.
If `gh`/network is unavailable, the check MUST FAIL-CLOSED (refuse) rather than proceed.

#### Scenario: current version already released -> blocked
- **WHEN** the current version is already tagged on the GitHub remote
- **THEN** `make bump-local` / `make release-prep` / `make loop-release` aborts before any bump/tag.

#### Scenario: no forward gap vs latest released -> blocked
- **WHEN** the current version does not advance past the latest released version (e.g. equal or lower)
- **THEN** the bump is blocked (no semver gap).

#### Scenario: current version unreleased and advances -> proceeds
- **WHEN** the current version has no remote tag and is greater than the latest released version
- **THEN** the flow proceeds and bumps to a new version (which cannot already be tagged).
