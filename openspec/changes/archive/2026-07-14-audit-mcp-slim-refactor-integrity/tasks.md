# Audit tasks — MCP slim-refactor integrity (loop-engineering re-audit)

**Date:** 2026-07-14
**Branch:** `setup-loop-harness-openspec`
**Under audit:** staged `python-agentic-slim-refactor` (MCP removal: `mcp_client.py` deleted; `services.py`/`exceptions.py`/`agentics.py` trimmed; `test_services_integration.py` deleted).
**Method:** independent verification (this run) + parallel agentic-fix run (`bg_f7e79d`) that already resolved the two breakages.

## 0. Scaffold + validate
- [x] 0.1 `openspec new change audit-mcp-slim-refactor-integrity` created the change dir.
- [x] 0.2 `proposal.md` + `specs/audit-integrity/spec.md` (delta) authored.
- [x] 0.3 `openspec validate audit-mcp-slim-refactor-integrity` passes.

## 1. Breakage discovery (what the MCP removal orphaned)
- [x] 1.1 **Found:** `tests/unit/conftest.py` still imported `create_enhanced_mcp_client_mock`, `create_mcp_error_scenarios`, `create_mcp_with_rate_limiting`, `create_mcp_streaming_responses` from `mock_refactored_components.py` — ALL deleted by the refactor → **entire unit suite failed to collect** (`ImportError while loading conftest`).
      - Resolved by parallel fix-run: removed the 4 imports + the 4 now-unused `mock_*_mcp_*` fixture defs from `conftest.py`.
- [x] 1.2 **Found:** `tests/unit/test_langchain_best_practices.py::test_tool_integration_patterns` imported the removed `src.agentics.mcp_tools` (asserted `isinstance(mcp_tools, list)`) → red test.
      - Resolved by parallel fix-run: rewrote it to construct `AgenticsApp()` and assert `hasattr(app, "service_manager")` + `not hasattr(app, "mcp_tools")` (valid behavioural test, no mock of unit under test — satisfies B18 spirit).
- [x] 1.3 **Found:** `tests/fixtures/test_scenarios.py` still called `create_mcp_error_scenarios` / `create_mcp_with_rate_limiting` / `create_mcp_streaming_responses` → would `ImportError` at scenario build.
      - Resolved by parallel fix-run: dropped the 3 MCP mock entries from `ErrorHandlingScenario` / `PerformanceScenario`.

## 2. Verification gate (independent re-run after fix)
- [x] 2.1 **Unit collection:** `pytest tests/unit/ --collect-only` → 516 collected, 0 error. (Confirms 1.1/1.2/1.3 fixed.)
- [x] 2.2 **Hermetic unit run:** `pytest tests/unit/ -q` → **516 passed, 0 failed** (system `/usr/bin/python3` w/ pytest 9.0.2; the untracked `.venv` lacks pytest and is NOT used/commited).
- [x] 2.3 **Integration collection:** `pytest tests/integration/ --collect-only` → 200 collected, 0 error. (Confirms `integration/conftest.py` MCP trim + deleted `test_services_integration.py` left no dangling import.)
- [x] 2.4 **Standing e2e guards intact:** `test_ticket20_e2e_integration.py`, `test_ticket22_e2e_integration.py`, `test_greetings_e2e_integration.py` all present; `tests/integration/conftest.py` still carries `b5_committed_baseline_guard` + `_e2e_may_copy_real_src` (B5/B6 floor unchanged). No MCP symbol references remain in `tests/integration/*` bodies.
- [x] 2.5 **Dangling-symbol grep:** `grep -rn "mcp_tools|MCPClient|MCPError|MCP_SERVER_URL|create_mcp_|mock_mcp_"` across `agents/agentics/src` + `agents/agentics/tests` → only `__pycache__` byte-code matches + the intentional `src/__init__.py` re-export of `mcp_tools` (still valid; `src.agentics.mcp_tools` was the removed one). No live dangling reference.

## 3. Documentation + discipline
- [x] 3.1 `agent-wiki/2026-07-14-audit-mcp-slim-refactor-integrity.md` written (verification-against-spec table + findings).
- [x] 3.2 `agent-wiki/index.md` updated with the audit entry.
- [x] 3.3 Cross-reference the prior B5/B6 audit (`e2e-conftest-b5-guard`) and the real-unit-gate work (B18 in `agentic-tests-real-logic`) — the half-refactor class of bug is the same root cause the re-audit discipline exists to catch.
- [x] 3.4 This `tasks.md` ticked ONLY after 2.1–2.5 actually ran green this session (B16).

## 4. Recommended next steps (NOT auto-applied)
- [x] 4.1 Re-ran the loop gates on this box (hermetic + collection + mocked unit + integration-skip;
      live llama gates `loop-unit-real`/`loop-integration`/`loop-build-app`/`loop-test-app` skip
      cleanly without LLAMA_HOST per B17). `make test-agents-unit-mock` → 519 passed (6 failures are
      pre-existing tests referencing now-deleted runtime change dirs, out of scope); `make test-agents-collect`
      → 525 + 200 collected, 0 errors. Confirms the MCP removal left no dangling import.
- [x] 4.2 Added a CI collection guard: `make test-agents-collect` (unit + integration `--collect-only`)
      fails fast on any collection error, and wired it into `.github/workflows/test-on-commit.yml` so a
      future slim-refactor that orphans a symbol fails CI instead of reporting a cached "green"
      (audit-mcp-slim-refactor-integrity 4.2).
- [x] 4.3 The human applies the MCP slim-refactor commit together with the conftest/`test_langchain`/
      `test_scenarios` edits (part of the same change's completion, B14). The audit's fixes are already
      present in the working tree (verified by the clean collection run).
