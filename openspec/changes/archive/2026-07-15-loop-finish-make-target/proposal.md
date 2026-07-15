# Proposal: LoopFinishMakeTarget

## Why
The `loop-green-auto-squash-changelog` change (all tasks ticked) REQUIRES three Makefile
targets — `make loop-finish`, `make archive-all-complete`, `make assert-backlog-clear` — but
they were never actually written. The tasks were falsely marked done. Without `loop-finish`
the harness/loop cannot perform its green-gated release finalisation (archive-all → squash →
changelog → bump → format), and AGENTS.md / the skill referenced `loop-finish`/B23 while the
target was absent (B8 drift).

## What Changes
- Add `assert-backlog-clear`: FAILS CLOSED if any active OpenSpec change has an open `- [ ]` task.
- Add `archive-all-complete` (depends on `assert-backlog-clear`): archives every active change
  via `phase7-archive` (per-change B16 open-task gate).
- Add `loop-finish` (depends on `archive-all-complete`): chains `squash-commits` → `changelog`
  → `bump-from-changelog` → `changelog-format`. NO push (B4/B14). Run only after `make
  loop-harness` is green (B20 pre-flight).

## Capabilities
- `release-automation` (loops `loop-finish` into the green-gated finalisation sequence).

## Impact
- B8: AGENTS.md + `openspec-loop-harness` skill updated to describe the real `loop-finish`
  target (previously referenced a non-existent target). B20/B23 unchanged. No git commit/push
  from the loop (B4/B14).
