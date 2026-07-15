## ADDED Requirements

### Requirement: Containerised work-log emission in archive phase
The system MUST run `scripts/record-work.py` entirely inside the `unit-test-agents` container when
`make phase7-archive CHANGE=<x>` or `make record-work CHANGE=<x>` is invoked — no host `python3`
process may execute the script (B17).

#### Scenario: archive phase emits work-log without host python
- **WHEN** a user runs `make phase7-archive CHANGE=<x>` on a change with all tasks ticked
- **THEN** the B16 open-task check and the `record-work.py` work-log step both run via
  `$(call docker_run, ... unit-test-agents sh -c "...record-work.py...")`, the file
  `agent-wiki/YYYY-MM-DD-<x>.md` is written, `agent-wiki/index.md` gains a line, and NO host
  `python3 scripts/record-work.py` process is spawned.

### Requirement: Direct docker_run invocation (no indirection target)
The containerised execution MUST use `$(call docker_run, ...)` directly in the target recipe, NOT a
delegating `run-agentic-cmd` target, because a target's `$(1)` is always empty and would drop the
command into the container as `sh -c ""`.

#### Scenario: command reaches the container intact
- **WHEN** `make record-work CHANGE=<x>` is run
- **THEN** the container's `sh -c` receives the literal `cd /project && python3
  /project/scripts/record-work.py --change <x>` (no empty command), and the script executes and
  writes its output.

### Requirement: Best-effort stub fallback
When `hermes`/`openspec`/`git` are not on the container PATH, `record-work.py` MUST fall back to a
stub body, still write the wiki file, and the archive target MUST NOT fail open solely due to
missing prose drafting (B17 best-effort).

#### Scenario: best-effort stub fallback
- **WHEN** `hermes`/`openspec`/`git` are not on the container PATH
- **THEN** `record-work.py` falls back to a stub body, still writes the wiki file, and the archive
  target does not fail open solely due to missing prose drafting.
