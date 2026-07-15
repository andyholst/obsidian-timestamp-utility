# Tasks

- [x] 1.1 Remove the `run-agentic-cmd` target from the Makefile (its `$(1)` was always empty, silently
  dropping the container command to `sh -c ""`).
- [x] 1.2 Rewrite `record-work` to call `$(call docker_run, docker compose -f docker-compose-files/agents.yaml
  run --rm -e GIT_CONFIG_GLOBAL=/tmp/gitconfig -e HERMES_BIN=$(HERMES_BIN) -e HERMES_PROFILE=project-manager
  unit-test-agents sh -c "$(RECORD_WORK_CMD)")` directly (B17, no host python3).
- [x] 1.3 Rewrite `phase7-archive` B16 check + work-log step to use the same direct `docker_run` call
  (in-container B16 via `scripts/assert_no_open_tasks_cli.py`; in-container work-log via `$(RECORD_WORK_CMD)`).
- [x] 1.4 Remove `run-agentic-cmd` from `.PHONY`.
- [x] 2.1 VERIFY (real host run, background terminal): `make record-work CHANGE=doc-sync-gate` writes
  `agent-wiki/2026-07-15-doc-sync-gate.md` (651 bytes) + updates `index.md`, with no host-python
  process (log shows `unit-test-agents sh -c "cd /project && python3 /project/scripts/record-work.py ..."`).
  Test artifact removed afterward (doc-sync-gate is in-progress).
- [x] 2.2 `make -n record-work` / `make -n phase7-archive` parse cleanly; grep confirms zero
  `run-agentic-cmd` references remain.
- [x] 3.1 `openspec validate phase7-archive-containerized` passes.
- [x] 3.2 `check-docs-sync` stays GREEN (no B8 doc changes in this change; gate still passes).

## Deeper fix (user: "do it better — container must run the commands / access files")

- [x] 4.1 Diagnose the in-container gaps: `git` IS present but exits 128 (dubious ownership under
  rootless nerdctl uid remap); `openspec` is at `/project/node_modules/.bin/openspec` but not on
  PATH; `hermes` is a host-only CLI NOT in the `agentics` image.
- [x] 4.2 Fix `RECORD_WORK_CMD`: `export PATH=/project/node_modules/.bin:$$PATH` (openspec resolves)
  + `git config --global --add safe.directory /project` (git no longer exits 128). The project was
  already bind-mounted at `/project` (rw) — the real fix was PATH + git ownership, not the mount.
- [x] 4.3 VERIFY (real host run): `make record-work CHANGE=phase7-archive-containerized` now writes a
  REAL work-log — `Branch: enhance-squash-commits` (git) + `openspec validate ... is valid`
  (openspec) captured. Only the prose paragraph is a stub because `hermes` is not in the image.
- [x] 4.4 `hermes` prose drafting remains best-effort stub (host CLI, not in image). The substantive
  metadata is captured. Documented; wiring `hermes` into the image is a separate follow-up if desired.

## Hermes prose: mount attempt abandoned (permission constraint)

- [x] 5.1 Attempted bind-mounting the host `~/.hermes` (venv + project-manager profile) read-only at
  the same absolute path + `HERMES_BIN` default `$(HOME)/.hermes/hermes-agent/venv/bin/hermes` +
  `resolve_hermes()` helper (env -> PATH -> $HOME venv, agnostic). The venv's python symlinks to
  `~/.local/share/uv/...` so that dir was mounted too.
- [x] 5.2 REVERTED: bind-mount fails with `PermissionError [Errno 13]` — `~/.hermes` is mode 700
  (owner-only) and the container's remapped uid 1000 cannot read it under rootless nerdctl. The user
  forbade `chmod` on `~/.hermes`, so the mount path is a dead end. `HERMES_MOUNT`/`HERMES_BIN` reverted
  to empty; prose stays best-effort stub in-container. The agnostic `resolve_hermes()` helper is kept
  (it lets a caller pass a world-readable `HERMES_BIN` or bake hermes into the image later).
- [x] 5.3 Final verified state: `make record-work CHANGE=phase7-archive-containerized` writes a REAL
  work-log — `Branch:` (git) + `openspec validate ... is valid` (openspec) captured; only the prose
  paragraph is a stub. This is the permission-safe end state. No host python3 (B17).
