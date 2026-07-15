# Proposal: ArchiveRunsWorkLog

## Why
Today `phase7-archive` only asserts no open tasks (B16), checks the durable E2E harness (B1), and
runs `openspec archive`. It does **NOT** emit the Phase-7 work-log entry — that is a *separate*,
optional `make record-work CHANGE=<name>` step that `loop-finish` / `phase7-archive` never call.
The result: every archived change silently skips its `agent-wiki/` work-log entry unless the agent
manually remembers to run `record-work` afterward. This is the same class of "documentation gap"
that the B8 sync discipline exists to prevent.

## What Changes
- `Makefile` `phase7-archive` gains a final step that invokes `scripts/record-work.py --change $(CHANGE)`
  (reusing the existing `record-work` target's logic) AFTER `openspec archive` succeeds, so the
  work-log entry is written as part of archiving — no separate manual step.
- The `record-work` capability spec (in `openspec/specs/record-work/spec.md`) gains a requirement
  that the archive phase MUST trigger the work-log, with a scenario proving it.
- `AGENTS.md` Phase 7 and `hermes/skills/openspec-loop-harness.md` are updated so the documented
  Phase-7 close-out sequence states that `phase7-archive` auto-emits the work-log (B8 sync — the
  four harness artifacts keep agreeing).
- `make record-work CHANGE=<name>` remains callable standalone (unchanged behaviour).

## Capabilities
- `record-work` (extended): the Phase-7 work-log now auto-runs inside `phase7-archive`.

## Impact
- MUST NOT regress: B16 open-task gate, B1 E2E presence, B4/B14 (no git commit/push — `record-work`
  only writes `agent-wiki/` files), B9 permission floor.
- **B17 (all execution via docker compose):** `record-work` and the `phase7-archive` work-log step
  MUST run INSIDE the `unit-test-agents` container — NO bare host `python3`. The B16 open-task
  check is also containerised (via `scripts/assert_no_open_tasks_cli.py`). A host-python invocation
  is a regression and must be fixed.
- MUST NOT break `openspec archive`'s no-commit guarantee: `record-work` writes only wiki files.
- The new step is best-effort-safe: if `hermes -z` is unavailable the script falls back to a stub
  body (it already does), so the archive never fails open because prose drafting was unavailable.
- `phase7-archive`'s non-zero exit on a `record-work` failure is acceptable (it surfaces the gap)
  but the script's own stub fallback keeps it from failing solely due to an unreachable Hermes CLI.
