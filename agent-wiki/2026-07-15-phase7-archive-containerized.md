# phase7-archive-containerized — Work Log

**Date:** 2026-07-15
**OpenSpec Change:** `phase7-archive-containerized`
**Branch:** `enhance-squash-commits`

## Summary
The `archive-runs-work-log` integration broke because `make phase7-archive`/`record-work` delegated to a `run-agentic-cmd` Makefile target whose positional `$(1)` is always empty, so the container received `sh -c ""` and `record-work.py` never ran. This change deletes that indirection and calls `$(call docker_run, … unit-test-agents sh -c "$(RECORD_WORK_CMD)")` directly (the same pattern as the working `test-check-docs-sync`), keeping the work-log fully containerised per B17 with no host `python3`. A deeper pass also fixes the real in-container gaps (`openspec` off PATH, `git` exiting 128 on dubious ownership) so the work-log captures genuine `Branch:` + `openspec validate` metadata.

## Verification Against Spec
- Requirement "Containerised work-log emission in archive phase": verified by real host run (task 2.1) — `agent-wiki/2026-07-15-doc-sync-gate.md` (651 bytes) + `index.md` written via `unit-test-agents sh -c "cd /project && python3 /project/scripts/record-work.py …"`, no host-python process ✅
- Requirement "Direct docker_run invocation (no indirection target)": verified by tasks 1.1/1.4 (target + `.PHONY` removed), 2.2 (`make -n` parses cleanly, grep confirms zero `run-agentic-cmd` refs) and 4.3 (literal `sh -c` command reaches container intact) ✅
- Requirement "Best-effort stub fallback": verified by tasks 4.1–4.4 — `openspec`/`git` PATH + `safe.directory` fixes capture real metadata; `hermes` absent from image falls back to stub body and the wiki file still writes, archive does not fail open ✅

## Key Decisions
- Dropped `run-agentic-cmd` entirely rather than patching its argument forwarding — a target's `$(1)` can never carry a recipe-local command string, so the only correct fix was calling `docker_run` directly in `record-work` and `phase7-archive`.
- Dig deeper than the mount: the repo was already bind-mounted rw at `/project`; the true in-container blockers were `openspec` not on PATH (`/project/node_modules/.bin`) and `git` exiting 128 (dubious ownership under rootless nerdctl uid remap). `RECORD_WORK_CMD` now exports `PATH=/project/node_modules/.bin:$PATH` and runs `git config --global --add safe.directory /project`.
- Abandoned the `~/.hermes` bind-mount: it is mode 700 (owner-only) and the container's remapped uid 1000 hits `PermissionError [Errno 13]`; `chmod` on `~/.hermes` is forbidden, so prose drafting stays a best-effort stub in-container.
- Kept the agnostic `resolve_hermes()` helper (env → PATH → `$HOME` venv) so a world-readable `HERMES_BIN` or baking `hermes` into the image later enables real prose with no code change.
- Preserved B16 (in-container `assert_no_open_tasks_cli.py` gate, fails-closed), B9 (`b9-perms` prereq), B4/B14 (wiki files only, no git commit/push) throughout.

## Current Status
Complete — all tasks ticked, `openspec validate phase7-archive-containerized` passes, and `check-docs-sync` stays green (no B8 doc edits in this change).

## Recommended Next Steps
- None — archive.
- (Optional, separate change) Bake `hermes` into the `agentics`/`unit-test-agents` image (or pass a world-readable `HERMES_BIN`) so the prose paragraph is real instead of a stub — the `resolve_hermes()` wiring already supports it.
