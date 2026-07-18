# release-automation Specification

## Purpose
TBD - created by archiving change loop-release-automation. Update Purpose after archive.
## Requirements
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
This change adds Makefile mechanics only. It MUST NOT alter the deterministic floor or the 7
verification stages, and the hermetic agentic gates MUST remain green.

#### Scenario: hermetic gates still pass
- **WHEN** `make loop-collect` and `make loop-unit` run after the change
- **THEN** they pass (no agent Python source changed).

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

### Requirement: squashed commits MUST be valid typed Conventional commits (commitlint gate)
The `squash-commits` Makefile target MUST lint its drafted commit message with `commitlint`
(using `commitlint.config.cjs`) BEFORE `git commit` runs, and MUST fail-closed (restore
pre-squash state, abort, no commit) when the message is not a valid Conventional commit
(`type(scope): subject` where type ∈ feat|fix|docs|refactor|perf|test|chore|build|ci|style|revert).
This is the "tag it accordingly" that drives the CHANGELOG sections and the version-bump PART.

#### Scenario: squashed message passes commitlint
- **WHEN** `make squash-commits` drafts a message whose first line is `feat(loop): ...` and body is valid
- **THEN** commitlint passes, the one typed commit is created (not pushed), and history is one commit ahead of `main`.

#### Scenario: squashed message fails commitlint
- **WHEN** the drafted first line is untyped (e.g. `updated stuff`) or malformed
- **THEN** the target aborts, restores the pre-squash state (`git reset --quit <main>`), leaves no commit, and exits non-zero.

### Requirement: per-commit linting via a commit-msg git hook
The repository MUST ship a `commit-msg` git hook (under `git-hooks/`) that runs `commitlint` on
each commit message, and a `install-git-hooks` Makefile target that wires it into `.git/hooks`.
This gives per-commit Conventional-Commit linting (the "changelog lint on each commit").

#### Scenario: a malformed manual commit is rejected
- **WHEN** a developer runs `git commit -m "bad message"` (untyped)
- **THEN** the `commit-msg` hook runs commitlint and rejects the commit (non-zero exit), so the bad message never enters history.

#### Scenario: hooks install cleanly
- **WHEN** `make install-git-hooks` runs
- **THEN** `git-hooks/commit-msg` is symlinked/copied to `.git/hooks/commit-msg` and made executable.

### Requirement: canonical release-flow sequence (squash → bump → changelog), local only
The repository MUST provide a single `release-flow` Makefile target that runs, in order and LOCAL
only (no push, B14):
  1. `squash-commits` — one typed Conventional commit (commitlint-gated).
  2. `bump-local` — `check-released` guard → `bump-version` (Obsidian way: package.json +
     manifest.json + versions.json) → `tag-release` (LOCAL `v<version>` tag). `bump-version`
     refuses unless NEW plugin TS exists in `src/main.ts` vs `origin/main`.
  3. `changelog` — regenerate `CHANGELOG.md` so the new `## <version>` section is present (driven
     by the local `v<version>` tag).
  4. `release-notes` — refresh the README release-notes block to the new version.
This encodes the user's flow: squash, then bump to the next unreleased version, then view it in
the changelog.

#### Scenario: full flow on a branch with new TS, version not yet released
- **WHEN** `make release-flow PART=patch` runs on a branch where `src/main.ts` differs from `origin/main` and the current version is not released / advances past latest released
- **THEN** one typed commit is created, the version is bumped (Obsidian way) + a local `v<version>` tag is made, `CHANGELOG.md` is regenerated with a new `## <version>` section, and README release-notes reflect it; nothing is pushed.

#### Scenario: bump refused when no new TS
- **WHEN** `make release-flow` runs but `src/main.ts` is unchanged vs `origin/main`
- **THEN** `bump-version` refuses to bump (no version change, no local tag), and the flow reports the no-op.

### Requirement: bump creates a LOCAL tag with no gap to the previous released version
`bump-local`/`release-flow` MUST create only a LOCAL git tag `v<version>` (no `git push`, B14), and
`check-released` MUST refuse if the bumped version does not advance past the latest released version
(no semver gap) or if it is already released on GitHub (tolerant of `X` and `vX` remote tag forms).

#### Scenario: no semver gap is blocked
- **WHEN** the current `package.json` version equals the latest released version (no forward gap)
- **THEN** `check-released` fails and the bump/tag is blocked.

#### Scenario: local tag only
- **WHEN** `bump-local` completes successfully
- **THEN** a local `v<version>` tag exists and `git status` shows no push was performed.

### Requirement: CHANGELOG regenerates to show the bumped version
The `changelog` target (reused by `release-flow`) MUST (re)generate `CHANGELOG.md` from git history
so the bumped `## <version>` section is viewable. The existing git_chglog template renders one
section per tag, so a local `v<version>` tag after bump yields the new section.

#### Scenario: changelog shows new version after bump+tag
- **WHEN** `make changelog` runs after `bump-local` created `v<version>`
- **THEN** `CHANGELOG.md` contains a `## <version>` heading with the squashed commit's categorized entries.

### Requirement: hermetic agentic gates still pass
Because this change adds Makefile/hook mechanics (not agent logic), the hermetic `loop-collect` and
`loop-unit` gates MUST remain green, and the deterministic floor + 7 verification stages MUST NOT
regress.

#### Scenario: hermetic gates still pass
- **WHEN** `make loop-collect` and `make loop-unit` run after the change
- **THEN** they pass (no agent Python source changed).

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

### Requirement: Review-approved loop-final finalisation

The system MUST provide a `make loop-final` target that finalises an open, human-approved PR by
squashing to one typed commit, regenerating the changelog from that commit, and force-pushing the
feature branch — permitted ONLY after explicit human approval and a fresh green loop-harness.

#### Scenario: Human approval unlocks squash + force-push

- **WHEN** a human explicitly approves an open PR (an approval phrase such as "PR looks great",
  "looks good", or "approved to finalize") and the agent runs `make loop-final BRANCH=<feat/...>
  APPROVED=1`
- **THEN** the target MUST run a fresh `make loop-harness`, require it GREEN, then run
  `squash-commits`, regenerate the CHANGELOG from the squash commit, and
  `git push --force-with-lease` the feature branch (never `main`).

#### Scenario: Fresh loop-harness must be green before any rewrite

- **WHEN** `make loop-final` is invoked
- **THEN** it MUST run `make loop-harness` FIRST and MUST abort (non-zero, no squash, no
  force-push) if any stage is not green — history is never rewritten on a red gate.

#### Scenario: No approval means no squash or force-push

- **WHEN** `make loop-final` is invoked WITHOUT the human approval flag (`APPROVED` unset)
- **THEN** it MUST refuse (fail closed) and perform no squash and no force-push, preserving the
  default B28a/B30b protection of an open PR.

#### Scenario: Force is scoped and revert stays forbidden

- **WHEN** `make loop-final` force-pushes
- **THEN** it MUST use `--force-with-lease` against the feature branch ONLY, MUST refuse to target
  `main`/`origin/main`, and MUST NOT run `git revert` (B30a remains absolute).

### Requirement: B8 doc-sync reflects loop-final behaviour

The system MUST keep all B8 sync docs describing the new `loop-final` behaviour identically and
MUST keep `make check-docs-sync` green with the updated behaviour range.

#### Scenario: check-docs-sync passes with the new behaviour

- **WHEN** `make check-docs-sync` runs after this change
- **THEN** it MUST pass, with AGENTS.md, the skill mirror, the docs reference, the Makefile, and
  `scripts/run-loop-harness.sh` all agreeing on the behaviour range and stage order.

