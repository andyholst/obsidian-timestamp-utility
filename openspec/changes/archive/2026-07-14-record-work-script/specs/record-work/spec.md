# record-work Specification

## ADDED Requirements

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
`commit` Makefile target's pattern), passing the collected change context as the prompt. The
script MUST fall back to a deterministic stub body if `hermes -z` returns empty output
(so the tool never fails open with no entry).

#### Scenario: hermes returns empty
- **WHEN** the `hermes -z` invocation returns no output
- **THEN** the script writes a valid entry using a deterministic stub (date + change name +
  note that prose drafting was unavailable) rather than erroring or writing an empty body.

### Requirement: Makefile target wraps the script
The Makefile MUST provide a `record-work` target that runs the script with `CHANGE` (and
optional `DATE`), with `b9-perms` as a prerequisite so the write targets are world-writable
under rootless nerdctl. The target MUST pass through the change name and refuse to run when
`CHANGE` is empty.

#### Scenario: make record-work invoked
- **WHEN** `make record-work CHANGE=<name>` runs
- **THEN** it applies the B9 permission floor, then invokes `scripts/record-work.py
  --change <name>`, and exits non-zero if the script fails.

### Requirement: B8 synchronization of documentation
AGENTS.md Phase 7 and the `openspec-loop-harness` skill MUST both reference `make
record-work` / `scripts/record-work.py` (not a missing `record-work` skill) for the
Phase-7 work-log step, so the four harness artifacts (Makefile / AGENTS.md / skill / script)
agree. No git commit/push is performed by the tool (B4/B14).

#### Scenario: documentation agrees
- **WHEN** a reviewer reads AGENTS.md Phase 7 and `hermes/skills/openspec-loop-harness.md`
- **THEN** both point the Phase-7 work-log step at `make record-work CHANGE=<name>` (or
  `scripts/record-work.py`), and neither references a `record-work` skill that does not exist.
