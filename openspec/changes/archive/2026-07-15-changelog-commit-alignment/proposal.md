# Proposal

## Why
After `make squash-commits` collapsed the branch into ONE commit
(`b81bf66 feat(loop): add deterministic integrator floor, release tooling, base64`),
the curated `CHANGELOG.md` was misaligned with the commit graph:
- It still carried a `## Unreleased` section populated with **leaked test/probe commits**
  (`feat(proof): unreleased probe commit`, `feat: test`, `feat: wipå`, and several bare
  `feat: ...`) that were never real work — they leaked from agent probe runs.
- It did NOT reflect the squashed commit's actual content (grouped by type), so the changelog
  and `git log origin/main..HEAD` disagreed.
- `make changelog` rendered raw `feat: ...` subjects instead of a clean `## Unreleased` whose
  bullets match the squashed commit, grouped by Conventional-Commit type.

The user requires the generated changelog to be **aligned with the squashed local commits**.

## What Changes
- `make changelog` regenerates `## Unreleased` from the **current commit graph** (after squash),
  so its bullets correspond to the single squashed commit, grouped by type (✨/🐞/📝/🛠️...).
- Leaked/garbage test commits are **never** persisted into the curated `CHANGELOG.md`.
- Alignment is verifiable: the top `## Unreleased` bullets are derived from `git log <base>..HEAD`
  (the same commits `make squash-commits` produced), not from pre-squash history.
- The recommended order is enforced in docs: `squash-commits` → `changelog` → `bump-from-changelog`,
  so the changelog always reflects the squashed state.

## Capabilities
- `release-automation` (changelog ↔ commit-graph alignment).

## Impact
- A green release ends with a `CHANGELOG.md` whose `## Unreleased` (or `## <next>`) section is a
  faithful, type-grouped reflection of the squashed commit — no test-leak garbage, no drift from
  `git log`.
