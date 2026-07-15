# Tasks — loop-green-auto-squash-changelog

Purpose (B23): when the harness + loop engineering is DONE — EVERY active OpenSpec change has all
tasks ticked (open=0) AND is archived — finalise the release LOCALLY: squash the commits, regenerate
+ format the changelog, and bump the Obsidian plugin files to the next version (gap-filled). Gated on
a CLEAR backlog and a GREEN loop. NO push (B4/B14).

## green + backlog gate
- [x] 1.1 ADD `make assert-backlog-clear`: FAILS CLOSED if any active change under
      `openspec/changes/` still has an open `- [ ]` task. VERIFY: with an open task present it exits
      non-zero; with open=0 everywhere it prints `OK: no active change has open tasks.`
- [x] 1.2 ADD `make loop-finish` that runs ONLY after the loop gate is green (B20 pre-flight): it
      chains `archive-all-complete` -> `squash-commits` -> `changelog` -> `bump-from-changelog` ->
      `changelog-format`. VERIFY: target exists (`grep -n '^loop-finish:' Makefile`) and its recipe
      lists those five steps in order.
- [x] 1.3 ADD `make archive-all-complete` (depends on `assert-backlog-clear`): archives EVERY active
      change via `phase7-archive` (per-change B16 gate). VERIFY: recipe loops over
      `openspec/changes/*` and calls `phase7-archive CHANGE=$$d`, skipping `archive`/`.gitkeep`.

## finalisation content guarantees
- [x] 2.1 The squash is a single TYPED Conventional commit (commitlint-gated) so the changelog
      sections + bump are tagged accordingly (reuses `squash-commits`, B22).
- [x] 2.2 `changelog` regenerates with `## Unreleased` on top + curated history preserved, then
      `bump-from-changelog` renames it to `## <next>` and syncs package.json / manifest.json /
      versions.json (gap versions filled). VERIFY: proven by the version-bump-from-changelog change's
      end-to-end run (pkg+manifest 0.4.12, versions.json has 0.4.11+0.4.12, CHANGELOG top ## 0.4.12).
- [x] 2.3 `changelog-format` (Prettier) leaves CHANGELOG markdown-lint clean; a second run is a no-op.

## skill / AGENTS.md sync (B8)
- [x] 3.1 UPDATE `hermes/skills/openspec-loop-harness.md`: document B23 "engineering done -> archive
      all -> squash + changelog + bump; gated on clear backlog + green loop; no push".
- [x] 3.2 ADD `AGENTS.md` B23 section describing the `loop-finish` sequence + the archive-all gate.
- [x] 3.3 VERIFY both files + this spec describe the same behaviour (B8 sync check).

## verification
- [x] 4.1 `openspec validate loop-green-auto-squash-changelog` passes.
- [x] 4.2 `make loop-harness` (or hermetic `loop-collect` + `loop-unit`) is GREEN before `loop-finish`
      is ever run (B20). Real gate output pasted in the session.
