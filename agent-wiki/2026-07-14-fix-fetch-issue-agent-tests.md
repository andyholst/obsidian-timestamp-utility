# fix-fetch-issue-agent-tests — Work Log

**Date:** 2026-07-14
**OpenSpec Change:** `fix-fetch-issue-agent-tests`
**Branch:** `setup-loop-harness-openspec`

## Summary
Triaged the 4 red tests from `make test-agents-unit` and made the agentic unit suite **100% green
and hermetic** (no live Ollama, no real `openspec new change` CLI writes during unit runs). Per the
project rule, valid-but-broken tests were **refactored** (not deleted); the only false alarm was
left alone. No production Python changed.

## Triage (dead vs valid)
| Test | Verdict | Action |
|------|---------|--------|
| `test_fetch_issue_agent_valid_url` | Valid — B15 seed-then-load bridge changed behaviour | Refactor: mock `create_change_from_issue` + `load_change`; assert `url` re-pointed to `openspec:<change>` |
| `test_fetch_issue_agent_closed_issue` | Valid — same | Refactor: same |
| `test_output_result_agent_*` (2) | False alarm — `-p no:logging` hid `caplog` fixture | No change (pass with standard config, 5/5) |
| `test_implementation_planner_agent*` (3) | Valid but non-hermetic (real `llm_reasoning` → live Ollama) | Refactor: inject mocked LLM `.invoke()` returning JSON |

## Tasks Completed
- Refactored `test_fetch_issue_agent_unit.py`: added `_mock_github_with_issue`; mocked the B15
  seed+load so no real change dirs are written. All 5 cases kept.
- Refactored `test_implementation_planner_agent_unit.py`: added `_mock_llm_with_json`; the 3 tests
  now inject a mocked LLM (hermetic, 0.02s vs ~9s live).
- Added `design.md` (classification table) to the OpenSpec change.
- Updated `agent-wiki/index.md`.

## Verification Against Spec
| Requirement | Result |
|---|---|
| FetchIssueAgent seed-then-load bridge unit-covered | PASS — 2 refactored tests assert seeded content + re-pointed url |
| No real CLI writes from unit tests | PASS — no `openspec/changes/ticket<N>` dirs created |
| ImplementationPlannerAgent tests hermetic | PASS — 3 tests inject mocked LLM, deterministic |
| Full suite green | PASS — **517 passed, 0 failed, 0 error** |

## Key Decisions
- **Do not delete valid tests.** Both failing groups test live graph nodes (`FetchIssueAgent`,
  `ImplementationPlannerAgent`). The correct fix is hermetic mocking, matching the existing
  `test_openspec_loader_seeding_unit` pattern.
- **No production change.** `FetchIssueAgent.process` (B15) and `ImplementationPlannerAgent.
  plan_implementation` (JSON merge) are correct; the bugs were in the tests, not the code.

## Current Status
Change complete and verified. Ready for `openspec archive fix-fetch-issue-agent-tests` (spec-only
merge). Commit/push is a deliberate human step (B4/B14).

## Recommended Next Steps
- Optionally run the integration/e2e gate once more (ticket20/22/greetings) to confirm the suite
  stays green end-to-end after the test refactor (unit tests are independent of those, but cheap).
