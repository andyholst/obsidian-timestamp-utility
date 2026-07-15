# Tasks — release-finalisation-commands

Purpose: prove `make squash-commits`, `make changelog`, `make bump-from-changelog` work, are
idempotent, survive corner cases, and bump the TS test file version. Each task RUNS a real command
and ASSERTS its output. Per B24, destructive/reset-capable verification runs in a throwaway worktree
(`git worktree add ../worktrees/<x> -b wt/<x>`), never on the parent.

## changelog
- [x] 1.1 `make changelog` produces a single `## Unreleased` section from unreleased work, no dup.
      VERIFY (in worktree): restore to main, run `make changelog`; `grep -c '^## Unreleased' CHANGELOG.md` == 1
      and the section lists the squashed commit grouped by type. ✅ DONE (verified on host: hash-stable x3).
- [x] 1.2 `make changelog` is idempotent (re-run does not duplicate).
      VERIFY: run `make changelog` a 2nd/3rd time; `grep -c '^## Unreleased' CHANGELOG.md` still == 1,
      byte-identical (md5 stable). ✅ DONE.

## bump-from-changelog
- [x] 2.1 `make bump-from-changelog` re-labels `## Unreleased` -> `## <next>` and bumps pkg+manifest.
      VERIFY (changelog first, then bump): top `## 0.4.11`, `package.json`==`manifest.json`==0.4.11. ✅ DONE.
- [x] 2.2 Idempotency: 3 consecutive runs keep the SAME version and ONE local `v<next>` tag.
      VERIFY: run 3x; pkg constant 0.4.11, `git tag | grep v0.4.11` count == 1, no v0.4.12. ✅ DONE.
- [x] 2.3 `versions.json` value is the REAL `minAppVersion`, not hardcoded.
      VERIFY: `versions.json['0.4.11']` == `manifest.json` minAppVersion `0.15.0`; gaps filled, semver-sorted. ✅ DONE.
- [x] 2.4 TS test file version bumped in lock-step.
      VERIFY: `grep "version:" src/__tests__/main.test.ts` == 0.4.11 (matches package.json). ✅ DONE.
- [x] 2.5 Corner: no unreleased work -> clean no-op, does not relabel released section.
      VERIFY: on tree where changelog top is `## 0.4.9` (released), run bump; it printed
      "top section '## 0.4.9' is released/curated -> not relabelled" and exited 0, version unchanged. ✅ DONE.

## squash-commits
- [x] 3.1 `make squash-commits` collapses branch commits to ONE typed Conventional commit (commitlint-gated).
      VERIFY (human-triggered by user on branch enhance-squash-commits): `git log --oneline origin/main..HEAD`
      shows exactly ONE commit `6792280 feat(loop-harness): release automation, squash-commits & base64 tool`
      with a valid `feat(...)` prefix. On an untyped Hermes draft the gate FAIL-CLOSED (proven in
      enhance-squash-commits 4.3). ✅ DONE (real run by user).

## docs/sync (B8)
- [x] 4.1 Behaviours reflected in `AGENTS.md` (B22/B23/B24) and `hermes/skills/openspec-loop-harness.md`.
      VERIFY: `make loop-finish` (green-gated: assert-backlog-clear -> archive-all-complete ->
      squash-commits -> changelog -> bump-from-changelog -> changelog-format) described consistently in
      both (B8 sync, loop-finish-make-target change). ✅ DONE.

## verification
- [x] 5.1 `openspec validate release-finalisation-commands` passes.
- [x] 5.2 `make loop-collect` + `make loop-unit` hermetic gates GREEN (B20) before archive.
      VERIFY (real host): `make loop-collect` -> 525 collected exit 0; `make loop-unit` -> 525 passed
      exit 0. ✅ DONE.
