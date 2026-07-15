# Tasks

## implement
- [x] 1.1 Add `assert-backlog-clear` target: FAILS CLOSED if any active change has an open `- [ ]` task.
      VERIFY: with open tasks present, `make assert-backlog-clear` exits non-zero and lists them
      (confirmed: enhance-squash-commits + release-finalisation-commands reported). ✅ DONE.
- [x] 1.2 Add `archive-all-complete` (depends on `assert-backlog-clear`): archives every active
      change via `phase7-archive`.
      VERIFY: `make -n archive-all-complete` parses; recipe loops `openspec/changes/*` calling
      `phase7-archive CHANGE=$$d`, skipping `archive`/`.gitkeep`. ✅ DONE.
- [x] 1.3 Add `loop-finish` (depends on `archive-all-complete`): chains squash-commits → changelog
      → bump-from-changelog → changelog-format. NO push (B4/B14).
      VERIFY: `make -n loop-finish` parses and lists the four steps in order. ✅ DONE.

## sync (B8)
- [x] 2.1 Update AGENTS.md B23 section to describe the REAL `loop-finish` target (was referencing a
      non-existent target). VERIFY: AGENTS.md + skill both name `loop-finish` / `archive-all-complete`
      / `assert-backlog-clear` and the same green-gated sequence. ✅ DONE.
- [x] 2.2 Update `hermes/skills/openspec-loop-harness.md` B23 to match. ✅ DONE.

## verification
- [x] 3.1 `openspec validate loop-finish-make-target` passes.
- [x] 3.2 `make assert-backlog-clear` correctly FAILS while open tasks remain (proves the gate works).
