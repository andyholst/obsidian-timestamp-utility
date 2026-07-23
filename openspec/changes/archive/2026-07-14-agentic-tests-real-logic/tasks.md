## 1. Scaffold the OpenSpec change
- [x] 1.1 Confirm `openspec/changes/agentic-tests-real-logic/` exists with `proposal.md`, `specs/agentic-tests-real-logic/spec.md`, `design.md`, and this `tasks.md`.
- [x] 1.2 Validate: `openspec validate agentic-tests-real-logic`.

## 2. Refactor unit tests to real logic (mock external only)
- [x] 2.1 `test_openspec_loader_seeding_unit.py` tests REAL `create_change_from_issue`/`github_url_to_change_name` with a mocked subprocess (external boundary only) — real artifact-writing logic asserted.
- [x] 2.2 `test_state_unit.py` / `test_code_generation_state_unit.py` assert REAL state transforms (no mock of the unit under test).
- [x] 2.3 `test_code_integrator_agent_unit.py` asserts REAL assembly output (mocks only the LLM client, an external boundary).
- [x] 2.4 `test_post_test_runner_unit.py` parses a REAL sample log with the real regex; asserts real counts (the pre-existing `\\d` regex bug was fixed so counts are real).
- [x] 2.5 `test_code_generator_agent_unit.py` / `test_test_suite_unit.py` build REAL prompts; mock ONLY the npm/llama boundary (`npm_list_tool` via the tool executor).
- [x] 2.6 Rule check: mocks wrap `subprocess`, `npm_list_tool`/`tool_executor`, `requests`, or the LLM client — never the function/class under test. Confirmed by inspection of the unit dir.

## 3. Make integration / e2e tests real calls
- [x] 3.1 Integration/e2e tests removed llama/GitHub `@patch`/`monkeypatch` on the LLM path; they point at REAL `LLAMA_HOST` (running llama) and assert on real generated TS.
- [x] 3.2 Issue-fetch tests use the REAL GitHub API (token-less public reads); `GITHUB_TOKEN` is NOT a skip condition (B17).
- [x] 3.3 `pytest -m e2e` / integration markers kept; tests REQUIRE llama and skip cleanly when `LLAMA_HOST` is absent (B17 skip rule).
- [x] 3.4 `make test-agents-unit` (live llama; unit under test never mocked) runs as the `loop-unit-real` gate (ordinal 2 of 6 in `loop-harness`). Both `loop-unit` (mocked) and `loop-unit-real` are reported (B18).

## 4. Post-run verification gate in the Makefile
- [x] 4.1 `verify-agentics-after-run` target added: runs `make test-agents-unit` + `make test-agents-integration` after `run-agentics`.
- [x] 4.2 Wired into AGENTS.md loop phase (5th "RE-RUN AGENTIC TESTS AFTER GENERATION") as a completion criterion after generation.
- [x] 4.3 The loop reports `agentic_tests_passed=False` + failing test name honestly if the re-run fails (the Makefile target fails non-zero, surfacing the failure; no silent green).

## 5. Verify against the spec
- [x] 5.1 `make test-agents-unit` runs on REAL implementations; mocks only around external calls (GitHub/llama/network/FS).
- [x] 5.2 `make test-agents-integration` makes REAL llama calls; skips cleanly without `LLAMA_HOST` (B17). No patched LLM/HTTP on the live path.
- [x] 5.3 `make verify-agentics-after-run` runs both suites (real unit gate passes 519; integration skips cleanly without llama).
- [x] 5.4 `make test-agents-unit` (real, non-mocked) runs AND is reported alongside — not instead of — `test-agents-unit-mock` (the hermetic mocked run). Both are gates 1 and 2 of `loop-harness`.

## 6. Document + decide
- [x] 6.1 `record-work` entry `agent-wiki/YYYY-MM-DD-agentic-tests-real-logic.md` with Verification Against Spec.
- [x] 6.2 Update `agent-wiki/index.md`.
- [x] 6.3 Archive: gates wired + verified; archive via `make phase7-archive CHANGE=agentic-tests-real-logic`.

## 7. Out-of-scope note (tracked under other changes)
- [x] 7.1 The 6 failing `unit` tests (`test_greetings_contract_unit.py`, `test_slim_refactor_invariants_unit.py`) reference change dirs (`greetings-modal-agentic-generation`, `uuid-modal-agentic-generation`) that were deleted at runtime (B4/B15 — never committed). They are dead tests and are addressed under `integration-tests-lifecycle` / `task-driven-ts-generation-e2e` pruning, not here.
