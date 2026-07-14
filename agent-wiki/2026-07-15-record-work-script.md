# record-work-script — Work Log

**Date:** 2026-07-15
**OpenSpec Change:** `record-work-script`
**Branch:** `setup-loop-harness-openspec`

## Summary
Replaced the missing `record-work` skill referenced in AGENTS.md Phase 7 with a deterministic, scriptable tool: `scripts/record-work.py` collects an OpenSpec change's context (`proposal.md`/`tasks.md`/`specs/**`, `openspec status` + `openspec validate`, git branch and recent commit, and a best-effort loop-gate summary) and calls the project-manager Hermes CLI (`hermes -z`) to draft the `agent-wiki` entry, then writes `agent-wiki/YYYY-MM-DD-<change>.md` and appends a line to `agent-wiki/index.md`. The tool is driven via `make record-work CHANGE=<name>` (with a `b9-perms` prerequisite) so it fits the existing OpenSpec workflow, and AGENTS.md Phase 7 + the `openspec-loop-harness` skill were B8-synced to point at the script instead of the non-existent skill.

## Verification Against Spec
- Requirement "Scriptable work-log entry generation": Implemented in `scripts/record-work.py`; `make record-work CHANGE=record-work-script` wrote `agent-wiki/2026-07-15-record-work-script.md` with the Date / OpenSpec Change / Branch / Summary / Verification Against Spec / Key Decisions / Current Status / Recommended Next Steps sections and appended a line under `## Change Entries` in `agent-wiki/index.md`; the missing-change guard (task 2.2) exits non-zero and writes no file. ✅
- Requirement "hermes CLI drives the prose": `scripts/record-work.py` invokes `hermes -z` with the `project-manager` profile (mirroring the existing `squash-commits` Makefile target) and falls back to a deterministic stub body when `hermes -z` returns empty (task 2.3), so the tool never writes a blank entry. ✅
- Requirement "Makefile target wraps the script": `record-work` target added with `b9-perms` prerequisite and a `CHANGE`-empty refusal (task 3.1); `make record-work CHANGE=record-work-script` is the live verification run. ✅
- Requirement "B8 synchronization of documentation": AGENTS.md Phase 7 (task 4.1) and `hermes/skills/openspec-loop-harness.md` (task 4.2) now reference `make record-work CHANGE=<name>` / `scripts/record-work.py`; neither cites a missing `record-work` skill; the tool performs no commit/push (B4/B14). ✅

## Key Decisions
- Used `hermes -z` (project-manager profile) to draft prose — same pattern as the existing `squash-commits` Makefile target — keeping the wiki voice consistent and the drafting logic out of Python.
- Added a deterministic stub fallback so an empty `hermes -z` response still yields a valid, non-empty entry (date + change name + "prose drafting unavailable" note) rather than erroring or writing a blank body.
- Wired `b9-perms` as a prerequisite of `record-work` so the `agent-wiki/` writes succeed under rootless nerdctl (world-writable floor), avoiding the `Errno 13` PermissionError that would otherwise hit container writes.
- Deliberately omitted a `design.md`: the change is a single self-contained script plus Makefile target, so the 3/4 artifact status (design not created) is intentional, not a gap.
- No git commit/push by the tool (B4/B14): the target writes only `agent-wiki/` files; landing the wiki entry is a deliberate human step.

## Current Status
Complete (openspec validate passes; 3/4 artifacts — design intentionally omitted; all four spec requirements satisfied).

## Recommended Next Steps
- Run `make phase7-archive CHANGE=record-work-script` to archive the change (B16 open-task guard runs `assert_no_open_tasks` before `openspec archive -y`) — tick every `tasks.md` checkbox first.
- None beyond archive: the script, Makefile target, and B8 doc-sync are in place and verified.
