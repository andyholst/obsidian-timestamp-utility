# Tasks — fix-fetch-issue-agent-tests

## 1. Triage
- [x] 1.1 Confirm the 2 `test_fetch_issue_agent_*` failures are valid tests of the live B15 bridge
      (not dead, not a production bug) — done via full traceback.
- [x] 1.2 Confirm `test_output_result_agent_*` errors were a `-p no:logging` fixture false alarm
      (pass with standard config) — no change needed.
- [x] 1.3 Confirm `test_implementation_planner_agent*` failures are a live-Ollama dependency
      (non-hermetic, valid tests) — refactor to mock the LLM.

## 2. Refactor the valid tests (hermetic, no live services)
- [x] 2.1 Refactor `test_fetch_issue_agent_valid_url` + `test_fetch_issue_agent_closed_issue` to mock
      `create_change_from_issue` + `load_change`; assert `ticket_content` from seeded change and
      `url` re-pointed to `openspec:<change>`.
- [x] 2.2 Add `_mock_github_with_issue` helper; keep all 5 cases (valid/invalid/empty/error/closed).
- [x] 2.3 Refactor `test_implementation_planner_agent` + `_no_npm_needed` + `_complex_ticket` to inject
      a mocked LLM (`.invoke()` returns JSON); no live Ollama. Add `_mock_llm_with_json` helper.
- [x] 2.4 Verify no real `openspec/changes/ticket<N>` dirs are created during the run.

## 3. Verification
- [x] 3.1 `pytest tests/unit/test_fetch_issue_agent_unit.py tests/unit/test_output_result_agent_unit.py`
      = 7/7 green, no stray dirs.
- [x] 3.2 `pytest tests/unit/test_implementation_planner_agent_unit.py` = 3/3 green in 0.02s (hermetic).
- [x] 3.3 Full `tests/unit/` = 100% green (517 passed, 0 failed, 0 error) — confirmed after both refactors.
- [x] 3.4 `openspec validate fix-fetch-issue-agent-tests` clean.

## 4. Document + archive
- [x] 4.1 `design.md` not required (test-only change); proposal + spec + tasks suffice.
- [x] 4.2 Update `agent-wiki/2026-07-14-fix-fetch-issue-agent-tests.md` with Verification Against Spec.
- [x] 4.3 `openspec archive fix-fetch-issue-agent-tests` (spec-only merge).
- [x] 4.4 Update `agent-wiki/index.md`.
