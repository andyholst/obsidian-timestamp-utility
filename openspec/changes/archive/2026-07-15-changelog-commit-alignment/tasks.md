# Tasks — changelog-commit-alignment

Goal: CHANGELOG.md's Unreleased section must be ALIGNED with the squashed local commit
(`b81bf66 feat(loop): ...`), with no leaked test/probe commits. Each task RUNS a command and
ASSERTS output. Per B24, destructive/reset-capable verification runs in a throwaway worktree.

## current misalignment (to fix)
- CHANGELOG.md `## Unreleased` lists leaked probe commits: `feat(proof): unreleased probe commit`,
  `feat: test`, `feat: wipå`, several bare `feat: ...`. These are NOT real work.
- It does NOT reflect `b81bf66` content grouped by type.
- `git log origin/main..HEAD` = exactly `b81bf66 feat(loop): add deterministic integrator floor,
  release tooling, base64`.

## fix + verify
- [x] 1.1 Scrub leaked test/probe commits from the curated CHANGELOG.md (never persist
      `feat(proof)`, `feat: test`, `feat: wipå`, bare `feat: ...`).
      VERIFY: `grep -nE "feat\(proof\)|feat: test|feat: wip|feat: \.\.\." CHANGELOG.md` returns
      nothing. ✅ DONE — leaked=0 after fix.
- [x] 1.2 `make changelog` regenerates `## Unreleased` from the squashed commit graph.
      VERIFY (in worktree): run `make changelog`; top is `## Unreleased`, bullets correspond to
      `b81bf66` grouped by type — no raw leaked `feat: ...` lines. ✅ DONE.
- [x] 1.3 Alignment proof: `## Unreleased` bullets derivable from `git log <base>..HEAD`.
      VERIFY: `feat(loop): add deterministic integrator floor, release tooling, base64` (b81bf66)
      present in `## Unreleased`; `grep -c '^## Unreleased' CHANGELOG.md` == 1. ✅ DONE.
- [x] 1.4 Idempotency: re-run `make changelog` keeps alignment (no duplicate headings, no drift).
      VERIFY: run 2nd/3rd time; `grep -c '^## Unreleased'` still == 1; leaked stays 0; b81bf66
      still reflected. ✅ DONE (3x in worktree).
- [x] 1.5 Order documented: `squash-commits` -> `changelog` -> `bump-from-changelog`.
      VERIFY: commits b81bf66 (squash) then changelog regeneration reflect the squashed state;
      root cause (git-chglog full-log dragged leaked commits) fixed in gen_changelog.sh.

## root cause (found during fix)
- git-chglog 0.15.4 range mode (`<tag>..HEAD`) errors "could not find the tag" here; its
  full-log mode grouped OFF-BRANCH leaked probe commits (feat(proof) etc.) under the nearest
  tag, so the changelog was misaligned with the real branch. gen_changelog.sh now renders the
  Unreleased section from `git log <latest-tag>..HEAD` grouped by type (reliable, aligned).
- The bogus local `v0.4.11` tag (a test artifact pointing at leaked probe commit f7d9a17) was
  deleted so the latest-tag computation resolves to the real `0.4.10`.

## verification
- [x] 2.1 `openspec validate changelog-commit-alignment` passes.
- [x] 2.2 `make loop-collect` + `make loop-unit` hermetic gates GREEN (B20) before archive.
      VERIFY (real host): `make loop-collect` -> 525 tests collected, exit 0; `make loop-unit` ->
      525 passed, 0 failed, exit 0. ✅ DONE.
