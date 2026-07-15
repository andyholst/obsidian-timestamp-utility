# Tasks — enforce-task-completion-gate

## 1. Scaffold the change
- [x] 1.1 `openspec/changes/enforce-task-completion-gate/` exists with proposal/spec/design/tasks.
- [x] 1.2 `openspec validate enforce-task-completion-gate` passes.

## 2. Python guard (`openspec_loader`)
- [x] 2.1 Add `open_task_count(change, project_root=None)` that parses `tasks.md`, counts
      unchecked `- [ ]` items, and ignores lines inside fenced ``` code blocks.
- [x] 2.2 Add `assert_no_open_tasks(change, ...)` that raises `RuntimeError` (REFUSE archive)
      listing the open count + unchecked lines when any open task exists.
- [x] 2.3 Unit-test both helpers in `tests/unit/test_enforce_task_completion_unit.py`
      (counts unchecked only; ignores fenced blocks; raises/passes correctly). Passes.

## 3. Makefile enforcement
- [x] 3.1 `phase7-archive` now runs `assert_no_open_tasks` BEFORE `openspec archive`
      (fails-closed: non-zero exit, no spec merge) — behaviour **B16**.
- [x] 3.2 Add `make loop-tasks` target: prints open/done counts per active change,
      surfacing changes with open tasks first.
- [x] 3.3 Verify: `make phase7-archive CHANGE=<open-change>` is refused; `make loop-tasks`
      lists the backlog. (Verified on `makefile-cleanup` — REFUSE archive printed.)

## 4. Documentation / discipline rule (B8 sync)
- [x] 4.1 Add durable behaviour **B16** to `AGENTS.md` and
      `hermes/skills/openspec-loop-harness.md`: the agent ticks each task the moment it is
      verified, never leaves an active change with open tasks, and the archive gate enforces
      this fails-closed. The agent never stops clearing the backlog unless told to.
- [x] 4.2 `record-work` entry `agent-wiki/YYYY-MM-DD-enforce-task-completion-gate.md` + index.

## 5. Verification
- [x] 5.1 New guard unit tests: 6 passed.
- [x] 5.2 `openspec validate enforce-task-completion-gate`: valid.
- [x] 5.3 B16 gate demonstrated: refuses `makefile-cleanup` (16 open); `loop-tasks` shows backlog.
