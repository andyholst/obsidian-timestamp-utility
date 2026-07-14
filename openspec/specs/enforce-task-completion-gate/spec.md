# enforce-task-completion-gate Specification

## Purpose
TBD - created by archiving change enforce-task-completion-gate. Update Purpose after archive.
## Requirements
### Requirement: Archive gate refuses changes with open tasks
The archiving mechanism (the `phase7-archive` Makefile target and `openspec_loader.assert_no_open_tasks`) MUST refuse to archive an OpenSpec change while its `tasks.md` still contains any unchecked task item (`- [ ]`). The gate MUST fail closed (non-zero exit, no spec merge) and report the count of open tasks and the file paths, so a half-done change can never be silently archived.

#### Scenario: change has open tasks
- **WHEN** `make phase7-archive CHANGE=<name>` (or `openspec_loader.assert_no_open_tasks`) runs against a change whose `tasks.md` has one or more unchecked `- [ ]` items
- **THEN** the archive is refused (non-zero exit, no `openspec archive` invoked) and the command prints the open-task count and the unchecked line(s)

#### Scenario: change fully ticked
- **WHEN** the archive gate runs against a change whose `tasks.md` has zero unchecked items
- **THEN** the gate proceeds to `openspec archive <name>` (B4/B14 still honored: spec-only, no extra git commit beyond the archive's own spec merge) and the e2e durability check (B1) runs

### Requirement: Visible task-completion status across changes
The Makefile MUST provide a `loop-tasks` target that lists every active OpenSpec change with its open/done task counts, so the loop-engineering backlog is visible at a glance and the agent cannot lose track of half-done changes.

#### Scenario: status reported
- **WHEN** `make loop-tasks` runs
- **THEN** it prints, for each active change, the number of unchecked (`- [ ]`) and checked (`- [x]`) task items, sorted so changes with open tasks are surfaced first

### Requirement: Open-task count is parseable in Python
`openspec_loader` MUST expose `open_task_count(change)` that parses `tasks.md`, counts unchecked `- [ ]` items, and ignores task lines inside fenced code blocks (```), returning an integer.

#### Scenario: count excludes code fences
- **WHEN** `open_task_count(<change>)` is called and `tasks.md` contains `- [ ] x` inside a ``` fenced block plus 2 genuine unchecked items
- **THEN** it returns 2 (code-fenced items are not counted as open tasks)

