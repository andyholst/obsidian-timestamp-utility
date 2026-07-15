# harden-docker-run-oneshell — Work Log

**Date:** 2026-07-15
**OpenSpec Change:** `harden-docker-run-oneshell`
**Branch:** `enhance-squash-commits`

## Summary
Hardened the Makefile `docker_run` macro so it no longer silently drops subsequent recipe lines under `.ONESHELL`, and fixed `RECORD_WORK_CMD` to resolve both `git` and `openspec` via a literal PATH. The bare-`exit` bug had been breaking every multi-call target (`record-work`, `phase7-archive`, `loop-collect`, `regen-doc-sync-fixtures`), and the `PATH=node_modules/.bin:$PATH` clobber had been dropping `/usr/bin` so `record-work.py` lost its git branch/commit metadata.

## Verification Against Spec
- Requirement "docker_run continues subsequent recipe lines on success under .ONESHELL": implemented via `if [ $$_rc -ne 0 ]; then exit $$_rc; fi` (no bare `exit`); `openspec validate` green, but runtime multi-call verify tasks 3.1–3.3 not yet ticked ⚠️
- Requirement "docker_run works in non-tty / piped / background contexts": non-tty `script -qec "/bin/sh <heredoc-tmpfile>" /dev/null` PTY wrap retained for nerdctl's hardcoded `--tty`; confirmed in proposal/What Changes ✅
- Requirement "RECORD_WORK_CMD resolves git and openspec": `RECORD_WORK_CMD` now uses literal `/usr/bin` + `/project/node_modules/.bin` instead of `$PATH`-derived; `openspec validate` green ✅

## Key Decisions
- Replaced bare `exit $$_rc` (which killed the shared `.ONESHELL` shell yet reported exit 0) with `if [ $$_rc -ne 0 ]; then exit $$_rc; fi`, so success falls through to following recipe lines while non-zero still fails fast.
- Kept the `script -qec "/bin/sh <heredoc-tmpfile>" /dev/null` PTY wrap for the non-tty branch (nerdctl `compose run` hardcodes `--tty`, has no `-T`; the heredoc preserves inner quotes where `printf` would mangle them).
- Switched `RECORD_WORK_CMD` from `export PATH=/project/node_modules/.bin:$PATH` (clobbered `/usr/bin` → `git: not found`) to a literal `export PATH=/usr/bin:/project/node_modules/.bin:...` so both `git` and the `openspec` CLI resolve.
- Removed the temporary `zztest` diagnostic target from the Makefile (task 1.3).

## Current Status
Complete at the spec level (`openspec validate` green, implementation applied on branch `enhance-squash-commits`), but tasks.md checkboxes remain unticked and the optional `design` artifact is absent — pending B16 task-tick discipline and a real `make` verify pass before archive.

## Recommended Next Steps
- Tick tasks.md 1.1–1.3, 2.1–2.4, 3.1–3.3, 4.1–4.6, 5.1–5.2 with real `make` output captured (per B16: tick as you verify).
- Run `make record-work CHANGE=harden-docker-run-oneshell` end-to-end to confirm step1 (container) → step2 (host `hermes -z`) → step3 (container write) all execute and `agent-wiki/<date>-harden-docker-run-oneshell.md` is written with real git metadata and no `git: not found`.
- Resolve the `design` artifact (add or explicitly waive) so `openspec status` reaches 4/4, then `make phase7-archive CHANGE=harden-docker-run-oneshell`.
