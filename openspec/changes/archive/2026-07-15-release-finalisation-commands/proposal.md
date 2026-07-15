# Proposal

## Why
The release-finalisation commands (`make squash-commits`, `make changelog`, `make bump-from-changelog`)
were historically broken and non-idempotent: `make changelog` silently produced nothing (called a
non-existent `python -m git_chglog` module), `make bump-from-changelog` climbed the version on every
re-run (0.4.11 -> 0.4.12 -> ...) and piled up `v0.4.x` tags, and `versions.json` was filled with a
hardcoded `minAppVersion` instead of the real one. The TS test file (`src/__tests__/main.test.ts`)
mock-manifest `version:` literal was never bumped, so the test mock drifted from the real plugin
version. This change makes the three commands correct, idempotent, corner-case-safe, and keeps the
TS test version in lock-step.

## What Changes
- `make changelog` renders the new work as a `## Unreleased` section and OVERWRITE-merges it onto the
  curated history (no duplicate headings on re-run).
- `make bump-from-changelog` anchors the next version on the RELEASED state (highest tag merged into
  `origin/main`), re-labels `## Unreleased` -> `## <next>`, bumps `package.json` + `manifest.json` +
  the TS test file `version:` literal + `versions.json` (value = `manifest.json` `minAppVersion`), and
  re-points the local `v<next>` tag. Re-runs do NOT climb and do NOT create extra tags.
- `make squash-commits` squashes to one TYPED Conventional commit (commitlint-gated).
- Idempotency + corner cases are tested explicitly (re-run 3x, dirty tree, already-released refusals,
  no-unreleased-work, TS test file drift).

## Capabilities
- `release-automation` (the three finalisation commands + their guarantees).

## Impact
- A green loop reliably ends with a single squashed commit, a complete + clean changelog, a bumped
  plugin version, AND a bumped TS test mock version — with no push (B14) and no tag aggregation.
