# record-work Specification

## ADDED Requirements

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
