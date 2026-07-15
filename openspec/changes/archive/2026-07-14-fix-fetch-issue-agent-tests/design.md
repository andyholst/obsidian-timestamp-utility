# Design — fix-fetch-issue-agent-tests

## Scope
Pure test-refactor change. No production Python modified. Goal: make the agentic unit suite
100% green and hermetic (no live Ollama / no real `openspec new change` CLI writes during unit runs).

## Classification of the 4 originally-red failures
| Test | Verdict | Action |
|------|---------|--------|
| `test_fetch_issue_agent_valid_url` | Valid (B15 bridge changed behaviour) | Refactor: mock `create_change_from_issue` + `load_change` |
| `test_fetch_issue_agent_closed_issue` | Valid (same) | Refactor: same mock pattern |
| `test_output_result_agent_*` (2) | False alarm (`-p no:logging` hid `caplog`) | No change — pass under standard config |
| `test_implementation_planner_agent*` (3) | Valid but non-hermetic (live LLM) | Refactor: inject mocked LLM `.invoke()` |

## No production code changed
`FetchIssueAgent.process` (B15 seed-then-load) and `ImplementationPlannerAgent.plan_implementation`
(JSON merge) are correct; both are now covered by deterministic hermetic tests.
