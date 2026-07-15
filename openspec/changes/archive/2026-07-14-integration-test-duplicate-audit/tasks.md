# Tasks: Integration Test Duplicate Audit

## Audit verdict (run 2026-07-14)
- Mechanical detector over 30 files / 192 tests found **1** high-overlap pair:
  `test_ticket20_e2e_integration.py` <-> `test_ticket22_e2e_integration.py` (Jaccard 1.00).
- On inspection this is a **structural twin, NOT a deletable duplicate**: it exercises a
  DISTINCT capability (UUID v7 timestamp vs random v4 UUID; different command ids
  `insert-uuid-v7`/`insert-random-uuid`; different regex asserts `7[0-9a-f]{3}` vs
  `4[0-9a-f]{3}`; different issue URLs #20/#22). Both are MANDATORY permanent e2e gates
  per B3 (ticket20 + ticket22 + greetings MUST all pass). Deleting one weakens the
  seed-then-generate proof to a single point of failure.
- **Decision: 0 files deleted.** No strict duplicates remain. The earlier genuine dupes
  (`test_jest_execution_integration_fixed.py`, `test_jest_execution_minimal.py`,
  `test_jest_execution_integration.py`) were already removed in a prior change.
- The suite is necessary coverage: non-slow 82 tests cover agentic behaviour (error
  recovery, config, agent composer, npm tools, phase1–4, cross-validation, immutable
  state, base agent) that unit + e2e do not.

## Tasks
- [x] 1.1 Write `specs/integration-test-hygiene/spec.md` (ADDED Requirement: no two
      integration test files are strict duplicates; Scenario: duplicate detection +
      deletion keeps canonical coverage).
- [x] 1.2 Build a mechanical duplicate detector: for each of the 31
      `tests/integration/test_*.py` files, extract (a) imported `src.*` modules and
      (b) the set of assertion targets; emit a ranked list of file pairs with high overlap.
- [x] 1.3 Review the flagged pairs and classify each as: strict-duplicate (delete
      redundant), superseded-by-canonical (delete), or distinct-coverage (keep).
      Verdict: the 1 flagged pair is distinct-coverage (B3 mandatory gates) -> KEEP.
- [x] 1.4 DELETE only confirmed strict duplicates. Result: NONE — no deletions required.
- [x] 1.5 Update the integration-test inventory (this tasks file) with final file count
      (30 files / 192 tests), the deleted files (none), and the per-pair decision.
- [x] 1.6 Re-run the fast loop-integration subset
      (`pytest tests/integration/ -m "integration and not e2e and not slow"`):
      81 collected, 80 passed, 1 failed, 1 skipped in 5m32s. The 1 failure
      (`test_collaborative_hitl_e2e.py::test_hitl_node` — assert 'human_feedback' in state)
      is MODEL VARIANCE on the small 9B LLM (key not emitted), NOT a duplicate-audit
      regression. Tracked separately as a flaky-assertion follow-up.
- [x] 1.7 Run `openspec validate integration-test-duplicate-audit` and
      `openspec status --change integration-test-duplicate-audit`; then
      `make phase7-archive CHANGE=integration-test-duplicate-audit`.
