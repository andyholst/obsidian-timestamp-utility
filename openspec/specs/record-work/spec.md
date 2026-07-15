# record-work Specification

## Purpose
Scriptable OpenSpec-change → agent-wiki work-log entry. Replaces the never-created `record-work`
skill referenced by AGENTS.md Phase 7: `scripts/record-work.py` (run via `make record-work
CHANGE=<name>` — inside the `unit-test-agents` container, per B17) collects a change's
proposal/tasks/specs + openspec status/validate + git branch/commit, drafts the prose with the
project-manager Hermes CLI (`hermes -z`), and writes `agent-wiki/YYYY-MM-DD-<change>.md` + updates
`agent-wiki/index.md`. No git commit/push (B4/B14).
## Requirements
### Requirement: Scriptable work-log entry generation
The system MUST provide a script (`scripts/record-work.py`) that, given an OpenSpec change
name, generates a dated work-log entry under `agent-wiki/` in the existing hand-written
format, using the project-manager Hermes CLI (`hermes -z`) to draft the prose from collected
change/gate context. The script MUST NOT require any live LLM endpoint beyond the `hermes`
CLI invocation (which runs locally).

#### Scenario: entry generated for a change
- **WHEN** `python3 scripts/record-work.py --change <name>` runs for an existing change `<name>`
- **THEN** it writes `agent-wiki/YYYY-MM-DD-<name>.md` (date = today unless `--date` is given)
  containing at least the sections: Date, OpenSpec Change, Branch, Summary, Verification
  Against Spec, Key Decisions, Current Status, Recommended Next Steps; and it appends one line
  to `agent-wiki/index.md` under `## Change Entries` linking the new entry.

#### Scenario: change does not exist
- **WHEN** the script runs with `--change <name>` where `openspec/changes/<name>` is absent
- **THEN** the script exits non-zero with a clear error naming the missing change and writes
  no wiki file.

### Requirement: hermes CLI drives the prose
`scripts/record-work.py` MUST obtain the entry's human-readable prose (Summary, Verification
Against Spec, Key Decisions, Current Status, Recommended Next Steps) by invoking
`hermes -z "<prompt>"` with the `project-manager` profile selected (matching the existing
`squash-commits` Makefile target's pattern), passing the collected change context as the prompt. The
script MUST fall back to a deterministic stub body if `hermes -z` returns empty output
(so the tool never fails open with no entry).

#### Scenario: hermes returns empty
- **WHEN** the `hermes -z` invocation returns no output
- **THEN** the script writes a valid entry using a deterministic stub (date + change name +
  note that prose drafting was unavailable) rather than erroring or writing an empty body.

### Requirement: Makefile target wraps the script (containerised)
The Makefile MUST provide a `record-work` target that runs the script with `CHANGE` (and
optional `DATE`), with `b9-perms` as a prerequisite so the write targets are world-writable
under rootless nerdctl, and MUST execute the script INSIDE the `unit-test-agents` container
via `docker compose` (no host `python3` — per B17). The target MUST pass through the change
name and refuse to run when `CHANGE` is empty.

#### Scenario: make record-work invoked
- **WHEN** `make record-work CHANGE=<name>` runs
- **THEN** it applies the B9 permission floor, then runs `scripts/record-work.py --change <name>`
  inside the `unit-test-agents` container, and exits non-zero if the script fails.

### Requirement: B8 synchronization of documentation
AGENTS.md Phase 7 and the `openspec-loop-harness` skill MUST both reference `make
record-work` / `scripts/record-work.py` (not a missing `record-work` skill) for the
Phase-7 work-log step, so the four harness artifacts (Makefile / AGENTS.md / skill / script)
agree. No git commit/push is performed by the tool (B4/B14).

#### Scenario: documentation agrees
- **WHEN** a reviewer reads AGENTS.md Phase 7 and `hermes/skills/openspec-loop-harness.md`
- **THEN** both point the Phase-7 work-log step at `make record-work CHANGE=<name>` (or
  `scripts/record-work.py`), both state that `phase7-archive` auto-emits the work-log entry on
  archive, and neither references a `record-work` skill that does not exist.

### Requirement: Archive phase MUST emit the work-log entry (containerised)
The system MUST run the Phase-7 work-log generation as part of `phase7-archive` (after
`openspec archive`), so every archived OpenSpec change automatically writes its
`agent-wiki/YYYY-MM-DD-<change>.md` entry and updates `agent-wiki/index.md` without a separate
manual step. `phase7-archive` MUST apply the B9 permission floor (via `b9-perms`) before invoking
`scripts/record-work.py --change $(CHANGE)` INSIDE the `unit-test-agents` container (no host
`python3` — all execution via docker compose, per B17). The standalone `make record-work
CHANGE=<name>` target MUST remain callable independently with unchanged behaviour (also
containerised). The work-log step MUST NOT perform any git commit/push (B4/B14) and MUST fall
back to a deterministic stub body if the `hermes -z` CLI is unavailable (so archive never fails
open due to missing prose drafting).

#### Scenario: archiving a change emits the work-log
- **WHEN** `make phase7-archive CHANGE=<name>` runs and the change passes the B16 open-task gate + B1 E2E gate and `openspec archive` succeeds
- **THEN** the target also runs `scripts/record-work.py --change <name>` (inside the unit-test-agents container, after applying the B9 floor), which writes `agent-wiki/YYYY-MM-DD-<name>.md` and appends a line to `agent-wiki/index.md`

#### Scenario: archive step is independent of manual record-work
- **WHEN** a user runs `make record-work CHANGE=<name>` directly
- **THEN** it behaves identically to before this change (B9 floor + containerised `scripts/record-work.py --change <name>`) and is not affected by the archive-wiring

#### Scenario: hermes CLI unavailable during archive
- **WHEN** `phase7-archive` runs but the `hermes -z` CLI returns no output
- **THEN** the work-log step writes a valid entry using the deterministic stub body (existing fallback) rather than failing the archive

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

### Requirement: TODO — name the requirement
The system MUST <describe the required behaviour in imperative form>.

#### Scenario: TODO — name the scenario
- **WHEN** <condition or action>
- **THEN** <expected outcome>

