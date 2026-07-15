# Proposal: ChangelogSectionsFromCommitType

## Why
`make changelog` must regenerate the `## Unreleased` section of `CHANGELOG.md` from the
actual branch commit graph (`<latest-tag>..HEAD`), grouping each entry under a section
derived from the commit's **Conventional-Commit type** — `feat` → ✨ New Features,
`fix` → 🐞 Bug Fixes, `chore` → 🛠️ Maintenance, etc. This guarantees the changelog is
always aligned with the (squashed) commit messages rather than stale hand-edited prose or
leaked test/probe commits.

## What Changes
- `scripts/gen_changelog.sh` renders `## Unreleased` from `git log <latest-tag>..HEAD`,
  parsing each commit's **subject line** (not body) with a Conventional-Commit regex and
  bucketing it into a type section. (git-chglog's range mode errors in this environment,
  so the git-log render is the reliable path; git-chglog is still tried first.)
- `scripts/merge_changelog.py` overwrites the working `## Unreleased` section (renames any
  `<tag> Latest` git-chglog output to `Unreleased`), never re-adding released versions, and
  collapses duplicate group headers / stray blank lines.
- Root cause fixes already applied: `docker_run` no longer passes inline paths to `script`
  (was `script: cannot open /project`), and the generated temp file is no longer empty
  (subject-vs-body parsing + correct `\s` regex).

## Capabilities
- `release-automation` (existing): CHANGELOG generation now reflects squashed commit types.

## Impact
- Must NOT regress: loop-harness gates (B20), deterministic floor (B11), no git
  commit/push from the loop (B4/B14). `make changelog` is a local, repeatable command.
- The section content is driven entirely by commit messages — to change changelog wording,
  change the commit message (or squash message), then re-run `make changelog`.
