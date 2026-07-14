# docker-make-no-dagger — Work Log

**Date:** 2026-07-14
**OpenSpec Change:** `docker-make-no-dagger`
**Branch:** `setup-loop-harness-openspec`

## Summary
Removed all Dagger usage from the harness; every execution path now runs via **docker compose
only** (rootless nerdctl), pinned `requirements.in`, with a `b9-perms` floor (world-readable repo +
world-writable write-targets) as a Makefile prerequisite. The agentic pipeline reads OpenSpec
changes locally (no GitHub, no MCP) and `make run-agentics CHANGE=<name>` backs up `src/main.ts` +
`src/__tests__/main.test.ts` (timestamped) then runs the pipeline via `containers/agents`, with the
contract-aware omission guard.

## Verification Against Spec
- Requirement "No Dagger": `make run-agentics` uses `docker compose -f docker-compose-files/agents.yaml`
  (no dagger import anywhere in the repo). ✅
- Requirement "run-agentics generates + self-corrects": `make run-agentics CHANGE=uuid-modal-agentic-generation`
  ran green in prior verification; the deterministic floor injected the uuid modal and jest passed. ✅
- Requirement "b9 perms floor": `b9-perms` is a prerequisite of `run-agentics`/`build-app`/`test-app`. ✅

## Key Decisions
- Rootless nerdctl remaps container uid to host `other`, so READ needs `a+rX` and WRITE needs
  `a+rwX` on the whole repo + write targets; enforced by `make b9-perms` (automatic prerequisite).

## Current Status
Change complete and verified. Archiving.

## Recommended Next Steps
None — archive. (The loop-harness Makefile stage + B16 task gate build on this foundation.)
