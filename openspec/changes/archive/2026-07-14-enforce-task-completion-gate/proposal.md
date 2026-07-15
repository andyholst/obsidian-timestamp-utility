# Enforce task-completion discipline in the OpenSpec/loop-harness

## Why
A harness/loop-engineering audit (2026-07-14) revealed a systemic discipline failure:
the agent completed work **in code** but left OpenSpec `tasks.md` checkboxes unticked,
so 9 change directories accumulated in `openspec/changes/` (several with 0/`done` rows)
and were never archived. Worse, `make phase7-archive` (and `openspec archive`) will archive a
change **even when its `tasks.md` still has open `- [ ]` items** — there is no fails-closed
guard. This breaks the core loop-engineering invariant: *a change is "done" only when every
task it prescribes is actually finished and verified, and the agent must never stop until the
backlog is cleared (unless told to).*

The root cause is twofold:
1. **No enforcement** — the archive gate checks B1 (e2e harness present) and B4 (no git) but
   NOT "are all tasks complete?" A change with 12 open tasks archives cleanly.
2. **No per-task ticking discipline + no visibility** — there is no cheap command to see
   open-task counts across changes, so a half-done change is invisible until audited.

## What Changes
- Add a **fails-closed task-completion guard** to the archive gate (`phase7-archive` Makefile
  target AND `openspec_loader` Python helper) that refuses to archive any change with open
  `- [ ]` tasks.
- Add a **`make loop-tasks`** target that prints open/done task counts for every active change
  (visibility for the loop).
- Add a Python helper `openspec_loader.open_task_count(change)` (parse `tasks.md` for unchecked
  items, ignoring fenced code blocks) + a unit test.
- Document the discipline in AGENTS.md / skill (new behaviour **B16**): the agent ticks each
  task the moment it is verified, and never leaves an active change with open tasks; the
  archive gate enforces this.

## Capabilities
- `enforce-task-completion-gate` (new): archive-gate refuses open tasks + `loop-tasks` visibility.

## Impact
- `Makefile` (`phase7-archive`, new `loop-tasks`): archive now fails closed on open tasks.
- `agents/agentics/src/openspec_loader.py`: new `open_task_count` + `assert_no_open_tasks`.
- `agents/agentics/tests/unit/`: new test for `open_task_count`.
- `AGENTS.md` + `hermes/skills/openspec-loop-harness.md`: B16 discipline rule (B8 sync).
- No generated TS/app code touched (Python + Makefile + docs only — B10/B11 safe).
