## Why

This change was seeded from GitHub issue https://github.com/andyholst/obsidian-timestamp-utility/issues/1 (title: "feat: added timestamp commands for Obsidian notes"). The issue is fetched once, then mirrored as a LOCAL OpenSpec change so the rest of the agentic pipeline runs entirely offline against `openspec:ticket1` (the B3/B11 source-of-truth rule).

## What Changes

- Implement the behaviour requested by the issue via a new Obsidian command, registered in `src/main.ts` and implemented as an `obsidian.Modal` subclass.
- Generated/updated TypeScript lives in `src/main.ts` and `src/__tests__/main.test.ts` (the exact files `CodeIntegratorAgent` writes to via `PROJECT_ROOT`).

## Capabilities

### New Capabilities
- `feat-added-timestamp-commands-for-obsidian-notes`: Implements the request from the issue as a Modal-backed command.

### Modified Capabilities
<!-- No existing spec-level behavior changes. -->

## Impact

- Affected code: `src/main.ts` (new command + generator), `src/__tests__/main.test.ts`.
- Affected systems: the agentic pipeline (`make run-agentics`) and its LLM.
