# release-automation Specification

## ADDED Requirements

### Requirement: Plugin version bumps the Obsidian way
The repository MUST provide a `bump-version` Makefile target that increments the plugin version
using the Obsidian convention: it updates `package.json` `version`, `manifest.json` `version`, and
**appends `{"<new-version>": "<minAppVersion>"}` to `versions.json`** (preserving existing
entries). Default bump is patch; `PART=minor`/`PART=major` override. The new version MUST equal
the `node -p "require('./package.json').version"` value the `TAG` Makefile variable already
derives.

#### Scenario: patch bump updates all three version files
- **WHEN** `make bump-version` runs on version `0.4.10`
- **THEN** `package.json` and `manifest.json` `version` become `0.4.11`, and `versions.json`
  contains a `"0.4.11": "0.15.0"` entry (with prior entries intact).

#### Scenario: minor/major override
- **WHEN** `make bump-version PART=minor` runs on `0.4.10`
- **THEN** the version becomes `0.5.0` across all three files.

### Requirement: README release notes reflect the current version
The README MUST contain a release-notes section that states the current plugin version (matching
`manifest.json`) and recent changes, and a `release-notes` (or `record-work`) step MUST refresh it
when a release is produced. The README's existing heading/format MUST be preserved.

#### Scenario: release notes updated on release
- **WHEN** the post-green release flow runs
- **THEN** the README's release-notes section shows the new version (matching `manifest.json`) and
  a summary of changes, with no broken format.

### Requirement: CHANGELOG regenerates on release
The release flow MUST regenerate `CHANGELOG.md` (reusing the existing `changelog` target via
`git_chglog`) so it reflects the squashed commit history.

#### Scenario: changelog regenerated
- **WHEN** the post-green release flow runs
- **THEN** `CHANGELOG.md` is (re)written and contains the new release entry.

### Requirement: Commits squash and release is tagged locally (no push)
After the loop is green and the version bumped, the flow MUST run `squash-commits` (existing
target — one Angular commit, no push, B14) and then create a LOCAL git tag `v<version>`
(e.g. `v0.4.11`). Tagging MUST be local only — no `git push` (B14). Pushing remains a deliberate
human action.

#### Scenario: squash then local tag
- **WHEN** the post-green release flow completes
- **THEN** there is exactly one squashed commit for the change and a local `v<version>` tag exists,
  and `git status` shows no push was performed.

### Requirement: Release flow is a post-green loop-engineering stage, guarded
Release automation MUST run ONLY after `loop-test-app` (the 7th loop stage) is green, and ONLY when
new generated TS was actually produced (guard: skip if `src/main.ts` /
`src/__tests__/main.test.ts` are unchanged vs the last committed baseline). It MUST NOT run as part
of the 7-stage verification gate itself (those stages stay unchanged), and MUST NOT push.

#### Scenario: skipped when no generated TS changed
- **WHEN** the loop is green but `src/main.ts` / `src/__tests__/main.test.ts` are unchanged vs the
  committed baseline
- **THEN** the release stage is a no-op (no version bump, no tag).

#### Scenario: runs only after green loop
- **WHEN** `src/main.ts` / `src/__tests__/main.test.ts` changed AND the 7-stage loop is green
- **THEN** the release stage runs bump-version → release-notes → changelog → squash-commits →
  tag-release, in order.

### Requirement: Release change does not regress the agentic suite
Because this change adds Makefile/README/version-file mechanics (not agent logic), it MUST NOT
alter the deterministic floor or the 7 verification stages, and the hermetic agentic gates MUST
remain green.

#### Scenario: hermetic gates still pass
- **WHEN** `make loop-collect` and `make loop-unit` run after the change
- **THEN** they pass (no agent Python source changed).
