# release-automation Specification (enhanced: enhance-squash-commits)

## ADDED Requirements

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
