# audit-mcp-slim-refactor-integrity — Work Log
**Date:** 2026-07-14
**OpenSpec Change:** `audit-mcp-slim-refactor-integrity`
**Branch:** `setup-loop-harness-openspec`
**Under audit:** the staged `python-agentic-slim-refactor` (MCP capability removal).

## Summary
A loop-engineering **re-audit** of the MCP slim-refactor, in the same spirit as the prior
`e2e-conftest-b5-guard` audit that caught a hidden B5/B6 committed-source deletion. The MCP
refactor deleted `mcp_client.py`, trimmed `services.py`/`exceptions.py`/`agentics.py`, and deleted
`test_services_integration.py` — but left **unstaged references** behind, the classic half-refactor
that a cached "green" run hides. This audit probed collection + ran the hermetic suite, then recorded
the findings + the resolution as trackable OpenSpec tasks.

## Findings (the breakages the removal orphaned)
| # | Symptom | Root cause | Resolution |
|---|---|---|---|
| 1.1 | Entire **unit suite failed to collect** (`ImportError while loading conftest`) | `tests/unit/conftest.py` still imported `create_enhanced_mcp_client_mock`, `create_mcp_error_scenarios`, `create_mcp_with_rate_limiting`, `create_mcp_streaming_responses` — all deleted from `mock_refactored_components.py` | Parallel fix-run removed the 4 imports + their now-unused `mock_*_mcp_*` fixture defs |
| 1.2 | Red test `test_langchain_best_practices.py::test_tool_integration_patterns` | It imported the removed `src.agentics.mcp_tools` and asserted `isinstance(mcp_tools, list)` | Rewrote to build `AgenticsApp()` and assert `hasattr(app,"service_manager")` + `not hasattr(app,"mcp_tools")` (real behaviour, no unit-under-test mock) |
| 1.3 | `test_scenarios.py` would `ImportError` at scenario build | Still called `create_mcp_error_scenarios` / `create_mcp_with_rate_limiting` / `create_mcp_streaming_responses` | Dropped the 3 MCP mock entries from `ErrorHandlingScenario`/`PerformanceScenario` |

All three were resolved by the parallel agentic-fix run (`bg_f7e79d`), which was editing the same
files concurrently. This audit **verified** those fixes by re-running, rather than re-implementing them.

## Verification Against Spec (this change's `audit-integrity` capability)
| Requirement | Result |
|---|---|
| Audit gate before "green" (collect + hermetic run + e2e guards) | PASS — collection ran first and caught the breakages |
| No dangling removed-capability symbols | PASS — `grep` for `mcp_tools\|MCPClient\|MCPError\|MCP_SERVER_URL\|create_mcp_\|mock_mcp_` across `src`+`tests` → only `__pycache__` + the intentional `src/__init__.py` re-export of `mcp_tools` (still valid) |
| Unit collection | PASS — `pytest tests/unit/ --collect-only` → **516 collected, 0 error** |
| Hermetic unit run | PASS — `pytest tests/unit/ -q` → **516 passed, 0 failed** |
| Integration collection | PASS — `pytest tests/integration/ --collect-only` → **200 collected, 0 error** |
| Standing e2e guards intact | PASS — `ticket20`/`ticket22`/`greetings` e2e present; `b5_committed_baseline_guard` + `_e2e_may_copy_real_src` unchanged (B5/B6 floor safe) |
| Audit outcome recorded + tasks ticked as verified | PASS — this wiki + `tasks.md` ticked only after 2.1–2.5 ran green (B16) |

## Key Decisions
- **Re-audit discipline works:** running `--collect-only` *before* trusting "green" is what surfaces a
  half-refactor. A cached pass can hide a collection-level `ImportError` because collection only happens
  when you actually invoke pytest on the tree.
- **Coordination over clobbering:** a sibling subagent was editing the exact files. Re-read-after-edit
  + verify-by-running avoided a write conflict and double-fix.
- **B18 cross-link:** the real-unit-gate work (`agentic-tests-real-logic`) is the same "don't trust a mocked
  green" principle at the Ollama layer; this audit is its Python-collection-layer analogue.
- **No commit/push** (B4/B14): the MCP slim-refactor + the sibling's fix edits remain staged/unstaged
  for the human to commit together.

## Current Status
Audit complete and verified (hermetic + collection + e2e-guard gates). OpenSpec change `audit-mcp-slim-refactor-integrity` is valid (4/4) and its tasks are ticked. **Not** archived (this is a tracking/audit change; archive is optional — it carries no spec merge of its own beyond the audit capability record).

## Recommended Next Steps
- Run `make loop-harness` on a box with Ollama + GITHUB_TOKEN to confirm `loop-unit-real` / `loop-integration` / `loop-build-app` / `loop-test-app` stay green post-MCP-removal (this audit covered hermetic + collection only).
- Add a CI collection/`grep` guard so a future slim-refactor that leaves a dangling import fails fast.
- When the human commits the MCP slim-refactor, include the sibling fix-run's conftest/`test_langchain`/`test_scenarios` edits in the same commit (B14: new behaviour, all gates green).
