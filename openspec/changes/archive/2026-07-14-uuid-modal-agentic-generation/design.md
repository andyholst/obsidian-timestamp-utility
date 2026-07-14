# Design: uuid-v7-modal

## Overview

Add an "Insert UUID v7" command to the Obsidian plugin. The feature is produced
by driving the existing Python agentic pipeline (`agents/agentics`) through the
Makefile, executed inside a git worktree, exactly as the
`docs/openspec-engineering-loop-harness.md` phases prescribe.

## UUID v7 algorithm

A UUID v7 is a 128-bit value laid out as:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                          unix_ts_ms                           |  (48 bits)
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|          unix_ts_ms           |  ver  |        rand_a         |  (12 bits ts + 4 ver + 12 rand)
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|var|                        rand_b                             |  (2 var + 62 rand)
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                            rand_b                             |  (64 bits)
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

- **unix_ts_ms**: 48-bit big-endian milliseconds since the Unix epoch (current time).
- **ver**: 4 bits fixed to `0111` (7).
- **rand_a**: 12 bits from a CS random source.
- **var**: 2 bits fixed to `10` (variant 1).
- **rand_b**: 62 bits from a CS random source (62 + 64 = 126 bits randomness).
- Total random: 16-bit-equivalent sequence + 64 remaining ≈ secure randomness.
- Format: 8-4-4-4-12 hex with hyphens → 36 chars.

A dependency-free implementation uses `crypto.getRandomValues` (browser/obsidian)
for the random fields and `Date.now()` for the timestamp.

## Where the code lives (agentic contract)

The agentic `CodeIntegratorAgent` writes to `PROJECT_ROOT/src` and
`PROJECT_ROOT/src/__tests__` (it also patches `package.json`/`manifest.json` if a
dependency is needed). Therefore the generated artifacts are:

- `src/main.ts`: add `insert-uuid-v7` command + a `generateUuidV7()` function
  (mirrors the existing `generateTimestamp()` shape).
- `src/__tests__/main.test.ts`: add tests asserting the v7 format, version/variant
  bits, cursor insertion, and the no-active-editor Notice path.

## Local OpenSpec ingestion (no GitHub)

Instead of fetching GitHub issue #20, the pipeline ingests this change locally:

- `agents/agentics/src/openspec_loader.py` reads
  `openspec/changes/uuid-modal-agentic-generation/{proposal.md, tasks.md, specs/**}`
  and synthesizes a GitHub-issue-shaped `ticket_content` (URL `openspec:uuid-modal-agentic-generation`).
- `FetchIssueAgent` falls back to the loader when the input is a local change ref.
- `make run-agentics CHANGE=uuid-modal-agentic-generation` (or `URL=openspec:<name>`)
  runs it. **MCP is not required** and is removed from the Makefile/compose invocation.

## Loop / self-correction

The agentic pipeline already loops: `post_test_runner → error_recovery →
code_integrator`. On test failure it diagnoses and re-integrates, then re-verifies.
The OpenSpec verification (tasks 4.1–4.3) is the strict gate that defines "done".
