# Fix fetch-issue-agent tests (seed-then-load bridge)

## Why
`make test-agents-unit` reported 2 failing tests in `tests/unit/test_fetch_issue_agent_unit.py`
(`test_fetch_issue_agent_valid_url`, `test_fetch_issue_agent_closed_issue`). Investigation showed
they are **NOT dead and NOT a production bug** — they are valid tests of the live `FetchIssueAgent`
node (part of the `issue_processing` sub-graph), but they were written before the B15
seed-then-generate bridge was added. The agent now fetches a GitHub issue, **seeds a local
OpenSpec change** via `create_change_from_issue`, then `load_change`s *that* as the ticket content
(re-pointing `state["url"]` to `openspec:<change>`). The tests still asserted the old raw-issue-body
behaviour, so they broke. Per the project rule ("if valid, refactor; if dead, remove"), these are
valid and must be refactored to test the bridge deterministically (mock the seed + load, no real
CLI writes).

The other 2 apparent failures (`test_output_result_agent*`) were a **false alarm** — they depend on
the `caplog` fixture, which is unavailable only when pytest runs with `-p no:logging`. With the
standard config they pass (5/5 in that file). No change needed.

## Additional finding: `test_implementation_planner_agent*` non-hermetic
`tests/unit/test_implementation_planner_agent_unit.py` passed the **real** `llm_reasoning` client
(not mocked), so the 3 tests make a live Ollama call. In isolation they pass (~9s, when Ollama is
free); in the full suite they hang/flake under Ollama contention, leaving 1 failure. These are
**valid** tests of the live `ImplementationPlannerAgent` node — not dead, not a production bug —
but they must be **refactored to be hermetic** (mock the LLM `.invoke()`) so the suite is
deterministic and does not depend on a live model. No production-code change.

## What Changes
- Refactor `test_fetch_issue_agent_valid_url` and `test_fetch_issue_agent_closed_issue` to mock
  `create_change_from_issue` + `load_change` (B15 off-line path), asserting `ticket_content` comes
  from the seeded local change and `url` is re-pointed to `openspec:<change>`.
- Refactor `test_implementation_planner_agent`, `_no_npm_needed`, `_complex_ticket` to inject a
  mocked LLM whose `.invoke()` returns a realistic JSON planning response (hermetic; no live Ollama).
- Add shared `_mock_github_with_issue` / `_mock_llm_with_json` helpers; keep all existing cases.
- No production-code change — `FetchIssueAgent` (B15 bridge) and `ImplementationPlannerAgent` are
  correct; both are covered by the new hermetic tests.

## Capabilities
- `fetch-issue-agent-tests` (new) — deterministic unit coverage of the seed-then-load bridge.
- `implementation-planner-hermetic-tests` (new) — hermetic unit coverage of the planner LLM merge.

## Impact
- Scope: test files only (`test_fetch_issue_agent_unit.py`, `test_implementation_planner_agent_unit.py`).
- No generated TS, no OpenSpec spec bodies authored in Python (B10 holds).
