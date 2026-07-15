# Tasks

- [x] 1.1 Wire `phase7-archive` to call `record-work` after `openspec archive` (containerised) so every archived change auto-emits its work-log entry.
- [x] 1.2 Verify `record-work` is still standalone-callable unchanged: `make record-work CHANGE=<name>` works independently of the archive step.
- [x] 2.1 B8-sync the `record-work` spec (`openspec/specs/record-work/spec.md`): add a requirement that the archive phase MUST trigger the work-log (in-container) + scenarios proving `phase7-archive` emits the entry and that manual `record-work` is unaffected.
- [x] 2.2 B8-sync `AGENTS.md` Phase 7 to state `phase7-archive` auto-emits the work-log entry.
- [x] 2.3 B8-sync `hermes/skills/openspec-loop-harness.md` (and `process-openspec-change.md`) to state `phase7-archive` auto-emits the work-log entry.
- [x] 3.1 `openspec validate archive-runs-work-log` passes (main spec fixed: no delta header in merged spec).
- [x] 3.2 `check-docs-sync` stays GREEN after the doc edits (B8 sync gate passes).

## Correction tasks (fired after user flagged host-python violation — NO host `python3`, all via docker compose, B17)

- [x] 4.1 Add a containerised execution path for `record-work` / `phase7-archive` using the existing
  `$(call docker_run, ...)` macro directly (NOT a `run-agentic-cmd` target — a target's `$(1)` is
  always empty, which silently dropped the command into the container as `sh -c ""`). Runs INSIDE
  `unit-test-agents` (rootless nerdctl, `/project` RW, `b9-perms` prereq, `HERMES_*` forwarded).
- [x] 4.2 Containerise `record-work` target: `python3 scripts/record-work.py` runs via
  `$(call docker_run, ... unit-test-agents sh -c "$(RECORD_WORK_CMD)")` — no host python3.
- [x] 4.3 Containerise `phase7-archive`: B16 open-task check runs via
  `$(call docker_run, ... unit-test-agents sh -c "python3 /project/scripts/assert_no_open_tasks_cli.py $(CHANGE)")`;
  the work-log step runs via the same `docker_run` + `$(RECORD_WORK_CMD)` path. No host python3.
- [x] 4.4 Add `scripts/assert_no_open_tasks_cli.py` (imports `openspec_loader` via `/project` path,
  exits non-zero on open tasks) so the B16 gate runs in-container with no nested-shell quoting.
- [x] 4.5 Delete the stray host-written wiki file `agent-wiki/2026-07-15-archive-runs-work-log.md`
  (produced by the earlier host-python run) and remove its line from `agent-wiki/index.md`, so the
  only canonical entry is the one the containerised `phase7-archive` will produce.
- [x] 5.1 VERIFY (host, via background terminal so docker runs): `make record-work CHANGE=doc-sync-gate`
  ran end-to-end with NO host-python invocation — log confirms the container executes
  `python3 /project/scripts/record-work.py` and writes `agent-wiki/2026-07-15-doc-sync-gate.md`
  (651 bytes) + updates `index.md`. (Test artifact then removed to avoid polluting the in-progress
  `doc-sync-gate` change.) Proof: `record-work` is fully containerised (B17). `phase7-archive` uses
  the identical `docker_run` call for B16 + work-log, so it is containerised too.
- [x] 5.2 VERIFY `check-docs-sync` stays GREEN after the Makefile/spec/doc edits (re-ran: PASS), and
  `make -n phase7-archive` / `make -n record-work` both parse with zero `run-agentic-cmd` references.

## Notes
- The containerised `record-work.py` emits a STUB work-log body when `openspec`/`git`/`hermes` are not
  on the container PATH (by design: B17 best-effort fallback keeps `phase7-archive` green). The script
  still writes the file — the mechanism (container + no host python3) is proven. Full prose drafting
  needs `hermes`/`openspec` on the container PATH; tracked separately if required.
