## 1. Setup + validate
- [x] 1.1 `openspec/changes/integrator-merge-refactor/` exists with proposal/spec/design/tasks.
- [x] 1.2 `openspec validate integrator-merge-refactor` passes.

## 2. Refactor integrator (Plan B: anchor-based merge)
- [x] 2.1 Rewrite `_extract_balanced_blocks` to capture the full source line (incl. `export `)
      and add a unit test proving it returns `export class X`, not `class X`.
- [x] 2.2 Rewrite `integrate_code_deterministic` to merge via anchors: imports block, `onload()`
      closing `}`, `TimestampPlugin` closing `}`, file end. No global brace counting.
- [x] 2.3 Rewrite `_assemble_contract_features` to: normalise escaped newlines, strip contract
      command/Modal from both existing + LLM output, then inject the authoritative command into
      `onload()`, append top-level Modal at file end, and append generator method inside
      `TimestampPlugin`.
- [x] 2.4 Add real unit test `test_integrator_merge_unit.py` asserting: contract command count
      == 1, top-level Modal count == 1, generator method inside `TimestampPlugin`, no orphaned
      `export`, `len(merged) >= len(existing)`. (8 tests, pass in host + container)

## 3. Fix broken tests
- [x] 3.1 Fix `tests/unit/test_test_suite_unit.py` broken relative import.
- [x] 3.2 Fix pytest / pytest-asyncio mismatch: `asyncio_mode = auto` + bumped
      `pytest-asyncio>=1.4.0` in `requirements.in`, regenerated `requirements.txt`.

## 4. Remove dead modules
- [x] 4.1 Import-graph scan (44/45 reachable); `test_suite` is a tested utility, not dead.
- [x] 4.2 No tests target removed modules.

## 5. No hard-coded logic (B7/B10: contract from spec, not literals)
- [x] 5.1 Contract (id/name/Modal/generator) derived from the OpenSpec change via
      `_expected_contract_for_change` — NO hard-coded command string.
- [x] 5.2 The TS bodies (command / Modal / generator) are NO LONGER string literals in Python:
      they live in the change's `## Contract` fenced ```ts block and are PARSED by
      `_spec_driven_feature_for_contract` by `=== CONTRACT_* ===` markers. Python only merges.
- [x] 5.3 Generator method visibility is NOT hard-coded (no `private`/`public`).

## 6. Fix make exit-code masking (honest verification gate)
- [x] 6.1 `build-app` / `test-app` now capture + re-exit the container's real rc, so the
      loop-engineering gate is trustworthy (previously masked jest failures as rc=0).

## 7. B11: restore + self-correct via Python only (never edit TS by hand)
- [x] 7.1 `PreTestRunnerAgent` now signals `state["pre_test_failed"]` / `pre_test_returncode`
      when `npm test` exits non-zero, so the self-correct loop
      (`PreTestRunner` -> `error_recovery` -> `code_generator` -> `code_integrator`) can restore
      the generated TS and regenerate. Added the keys to `State` TypedDict.
- [x] 7.2 AGENTS.md **(B11)** documents: on generated-TS failure, RESTORE the TS code+tests to
      `backups/` or committed baseline, then FIX ONLY via Python (spec contract / LLM prompt /
      integrator / self-correct loop), never hand-edit TS. Synced to hermes skill (B10+B11).
- [x] 7.3 Reverted all direct TS edits (restored generated `main.ts`/`main.test.ts` to baseline);
      the broken LLM-generated `main.test.ts` is a known self-correct-loop gap (PreTestRunner
      jest-metric previously returned 0 — now fixed to signal failure).

## 8. Verify + document
- [x] 8.1 `make test-agents-unit-mock` passes: 494 passed, 3 pre-existing failures (stale
      fetch/planner assertions + 1 Ollama-required) — none touch the integrator.
- [x] 8.2 `make build-app` passes (tsc/rollup rc=0) for `uuid-modal-agentic-generation`.
- [x] 8.3 `make test-app` passes green: 3 suites / 62 tests passed, rc=0 (achieved after the
      Python-side fixes + spec contract; the earlier failure was LLM-generated broken tests,
      now covered by B11's restore-and-regenerate rule).
- [x] 8.4 `record-work` entry + `agent-wiki/index.md` update; recommend archive once 8.1–8.3 pass.
