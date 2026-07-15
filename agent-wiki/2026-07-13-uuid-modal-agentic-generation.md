# 2026-07-13 — uuid-modal-agentic-generation

## Date
2026-07-13

## OpenSpec Change
`uuid-modal-agentic-generation` (feature gen: generate TS `src/main.ts` + `src/__tests__/main.test.ts`
for an `insert-uuid-v7` command implemented as an `obsidian.Modal` subclass `UuidV7Modal`).

Coordinated with `agentic-architecture-test-refactor` (dead-code removal + sole-writer enforcement +
stale unit-test fixes). Per the user's rule, neither is "done" until BOTH are green.

## Tasks Completed
- 1.1–1.2 Scaffold + validate the change.
- 2.1–2.5 Pipeline reads the LOCAL OpenSpec change (`openspec:<name>`), no GitHub, no MCP.
- 3.1–3.3 generation run with the hardened deterministic floor:
  - 3.3.0 exact spec contract (`id: 'insert-uuid-v7'`, `name: 'Insert UUID v7 (timestamp-based)'`, `UuidV7Modal`).
  - 3.3.6 deterministic floor: LLM denied `write_file_tool`; Python `update_file`/`create_file`
    (→ `integrate_test_contract`) are the SOLE writer of generated TS.
- 4.1–4.5 verify against spec (tsc + jest green; spec-driven `## Test Contract` injection).
- 5.1–5.2 wiki entry + index (this file).

## Verification Against Spec (per-requirement result)
| Requirement / Scenario | Result | Evidence |
|---|---|---|
| Command `id: 'insert-uuid-v7'` wired in `main.ts` | PASS | `main.ts` grep: `id: 'insert-uuid-v7'` = 1 (attempt #10) |
| Command `name: 'Insert UUID v7 (timestamp-based)'` | PASS | injected verbatim from `## Contract` |
| `UuidV7Modal extends obsidian.Modal` generated + registered | PASS | `main.ts` `UuidV7Modal` count = 1 |
| `generateUuidV7(): string` generator landed inside `TimestampPlugin` | PASS | method definition present, no duplicate |
| v7 format regex `^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$` | PASS | jest test asserts it; suite green |
| Notice on no active editor | PASS | `obsidian.Notice` used (namespace import, no unused import) |
| No omission (file not smaller than backup) | PASS | merge floor appends, never replaces |
| `make build-app` (tsc) | PASS | rc=0 (attempt #10) |
| `make test-app` (jest) | PASS | rc=0 (24+ tests green, attempt #10) |
| B10 — no hard-coded TS bodies in Python | PASS | grep for TS-body literals in `src/*.py` returns only guards/comments |

**Final e2e (attempt #10):** `run-agentics rc=0`, `build-app rc=0`, `test-app rc=0`,
`RESULT: PASS`. Repeatedly green (resolves the earlier #6/#7 flaky split).

## Key Decisions
1. **Marker-based contract extraction.** `contract_ts` is now parsed from the unambiguous
   `=== CONTRACT_COMMAND|GENERATOR|MODAL ===` markers in `tasks.md` (NOT the fragile `## Contract`
   fence, which silently dropped the Modal block). Same for `test_contract_ts`.
2. **Unconditional presence-check backstop.** `_ensure_contract_present` (applied after
   `_assemble_contract_features`) asserts-and-appends the command/generator/Modal by simple
   presence checks — independent of per-run LLM `code_content` shape. This removed the
   run-to-run flakiness (#35). Fully idempotent (double-apply → exactly one of each).
3. **Self-contained Test Contract.** The spec `## Test Contract` instantiates its own
   `uuidPlugin` + `beforeEach` + `addCommand` override, so it never depends on file scope
   (`let plugin`/`beforeEach`) and can't be injected out-of-scope.
4. **Import hygiene.** `integrate_code_deterministic` drops a redundant `import { Notice } from 'obsidian'`
   when `import * as obsidian` is present and `obsidian.Notice` is used (avoids TS6133).
5. **LLM denied `write_file_tool` (B11).** The integrator's LLM tool set is `read_file_tool` +
   `check_file_exists_tool` only; `write_file_tool` kept for Python-internal config (package.json).

## Problems & Solutions
- **Non-deterministic merge (#35):** earlier attempts varied (`UuidV7Modal: 2` vs `0`). Root cause:
  injection routed through variable LLM output. Fixed with the unconditional `_ensure_contract_present`
  backstop (spec-marker-driven, not LLM-shape-driven).
- **`main.test.ts` `plugin` out of scope:** the old injection placed the spec `describe` before
  `let plugin`. Fixed by (a) injecting at the END of the top-level `describe`, and (b) making the
  Test Contract self-contained.
- **`Notice` unused import (TS6133):** contract used `obsidian.Notice` but the LLM added a redundant
  `import { Notice }`. Fixed by the deterministic import-dedup rule.
- **Stale unit tests:** removed `generate_filename` (dead code) and fixed `test_init_success`
  (2 tools, not 3) + `test_process_no_files_with_content`. Integrator unit suite now 22/22.

## Current Status
- `uuid-modal-agentic-generation`: all tasks done except 5.3 (gated archive — must archive together
  with `agentic-architecture-test-refactor` once BOTH are green).
- `agentic-architecture-test-refactor`: Python refactor (sole-writer, dead-code removal, unit-test
  fixes) landed; its tasks.md tracked. Gated archive pending.

## Recommended Next Steps
1. Run `make verify-agentics-after-run` (real unit + integration + validate-test_suite) for the
   final green gate on the architecture-refactor change.
2. When BOTH changes are green, archive together via `make phase7-archive CHANGE=uuid-modal-agentic-generation`
   (and the refactor change) — archive spec ONLY; never commit/push generated TS (human step).
3. Commit the Python/spec/doc changes separately (human step; the agent does not commit/push).
