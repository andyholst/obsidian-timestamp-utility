# enforce-task-completion-gate — Work Log

**Date:** 2026-07-14
**OpenSpec Change:** `enforce-task-completion-gate`
**Branch:** `setup-loop-harness-openspec`

## Summary
A harness/loop-engineering audit exposed a systemic discipline failure: the agent completed work
**in code** but left OpenSpec `tasks.md` checkboxes unticked, so **9 change directories** piled up
in `openspec/changes/` (several with 0/`done` rows) and were never archived. Worse, `openspec
archive` (and `make phase7-archive`) would archive a change **even with open `- [ ]` tasks** — no
fails-closed guard. This breaks the core loop-engineering invariant: a change is done only when
every task is finished, verified, AND archived; and the agent must never stop clearing the
backlog unless told.

## Root Cause
1. **No enforcement** — archive gate checked B1 (e2e present) and B4 (no git) but NOT
   "are all tasks complete?".
2. **No per-task ticking + no visibility** — no cheap way to see open-task counts across changes,
   so half-done changes were invisible until audited.

## Fix (this change)
- **Python:** added `openspec_loader.open_task_count(change)` (counts unchecked `- [ ]`, ignores
  fenced code blocks) + `assert_no_open_tasks(change)` (raises `RuntimeError` "REFUSE archive" with
  the open count + lines when any task is open). Unit-tested (6 cases, hermetic).
- **Makefile:** `phase7-archive` now runs `assert_no_open_tasks` BEFORE `openspec archive`
  (fails-closed: non-zero exit, no spec merge) — behaviour **B16**. Added `make loop-tasks` to list
  open/done counts per active change (backlog visibility).
- **Docs:** added durable behaviour **B16** to `AGENTS.md` and `hermes/skills/openspec-loop-harness.md`
  (B8 sync): tick each task the moment it is verified; never leave an active change with open tasks;
  keep grinding the backlog until archived; archive gate enforces fails-closed.

## Verification Against Spec
- Requirement "Archive gate refuses changes with open tasks": `make phase7-archive CHANGE=makefile-cleanup`
  (16 open tasks) → REFUSE archive, non-zero exit. ✅
- Requirement "Visible task-completion status": `make loop-tasks` lists all 9 changes with
  open/done counts, open-first. ✅
- Requirement "Open-task count parseable in Python": `open_task_count` ignores fenced blocks
  (unit test confirms 2 fenced `- [ ]` not counted). ✅

## Key Decisions
- Code-fenced `- [ ]` text inside `tasks.md` contract/code samples must NOT count as open tasks
  (a change's spec legitimately shows example unchecked steps inside ``` blocks).
- The guard raises before `openspec archive`, so no partial spec merge occurs on a half-done change.

## Problems & Solutions
- Pyright complained about `os.sys` import in the new test — fixed by `import sys` + `sys.path.insert`.
- Discovered `openspec archive` auto-commits the spec merge (visible as commits like `d4d27e2`,
  `1c60184`). This is the archive tooling's behaviour, not a manual `git commit`; B4/B14 still hold
  for *extra* commits. Flagged for the user.

## Current Status
Change complete and validated (`openspec validate` clean). Ready to archive. The B16 gate now
protects all future archiving; `loop-tasks` makes the remaining backlog (the other 9 changes) visible
so it can be ground down task-by-task.

## Recommended Next Steps
1. Archive this change (`make phase7-archive CHANGE=enforce-task-completion-gate` — open=0, will pass).
2. Resume the backlog: for each of the remaining 9 changes, verify work against code, tick real tasks,
   and archive via `make phase7-archive`. `uuid-modal-agentic-generation` (open=0) can be archived now.
