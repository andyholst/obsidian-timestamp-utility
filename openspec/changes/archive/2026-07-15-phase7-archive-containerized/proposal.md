# Proposal: phase7-archive-containerized

## Why
The integration that makes `make phase7-archive` auto-emit the `agent-wiki` work-log (change
`archive-runs-work-log`) was wired through a `run-agentic-cmd` Makefile **target**. A target's
positional `$(1)` is always empty, so the container received `sh -c ""` and `record-work.py` never
ran — the archive silently produced no work-log (and our earlier host `python3` attempt violated B17).

## What Changes
- Remove `run-agentic-cmd`; have `record-work` and `phase7-archive` call `$(call docker_run, docker
  compose ... unit-test-agents sh -c "$(RECORD_WORK_CMD)")` **directly** — the same pattern as the
  working `test-check-docs-sync` target. This guarantees the command reaches the container intact.
- B16 open-task gate also runs in-container via the same `docker_run` macro.
- No host `python3` anywhere (B17). `HERMES_*` forwarded so prose drafting can reach the CLI.

## Capabilities
- `record-work` (extended): `phase7-archive` + `record-work` execute inside `unit-test-agents`.

## Impact
- MUST NOT regress: B16 (fails-closed on open tasks), B4/B14 (no git commit/push — only wiki files
  written), B9 (`b9-perms` prereq). MUST stay containerised (B17 — no host python3).
- Behaviour unchanged for a human: `make phase7-archive CHANGE=<x>` still archives the spec AND writes
  `agent-wiki/YYYY-MM-DD-<x>.md` + updates `index.md`.
- Deeper fix (verified): the `agentics` container already bind-mounts the repo at `/project` (rw). The
  real in-container gaps were (a) `openspec` not on PATH (`/project/node_modules/.bin` not in PATH) and
  (b) `git` exiting 128 (dubious ownership under rootless nerdctl uid remap). `RECORD_WORK_CMD` now sets
  `PATH` and `git config --global safe.directory /project`, so `record-work.py` captures REAL metadata
  (branch, `openspec validate`). Verified: `make record-work` writes a real work-log with `Branch:` +
  `openspec validate ... is valid`.
- Hermes prose: `hermes` is a HOST-ONLY CLI (venv under `~/.hermes`, hardcoded absolute paths, mode 700).
  Bind-mounting it read-only into the container FAILS with `PermissionError` (container uid can't read the
  owner-only dir under rootless nerdctl), and `chmod` on `~/.hermes` is forbidden. So prose drafting stays
  best-effort stub in-container. The agnostic `resolve_hermes()` helper is kept so a world-readable
  `HERMES_BIN` (or baking hermes into the image) can enable real prose later without code changes.
