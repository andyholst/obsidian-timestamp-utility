## Why
A prior harness/loop-engineering re-audit (change `e2e-conftest-b5-guard`) surfaced a **real B5/B6 committed-source deletion** that an earlier "green" claim had hidden. That proved the suite can report green while silently leaving the repo broken. The current staged MCP slim-refactor (`mcp_client.py` removed, `services.py`/`exceptions.py`/`agentics.py`/`conftest.py`/`test_services_integration.py` trimmed) is exactly the kind of trans-file edit that hides a half-refactor: it deletes the symbols but left **unstaged references** behind. This change is the **audit + integrity gate** that proves the MCP removal is complete and the loop stays green — and records the new findings so the next session does not re-discover them.

## What Changes
- Adds an **audit OpenSpec change** that documents and verifies the MCP slim-refactor's completeness (no dangling `mcp_tools`/`MCPClient`/`create_enhanced_mcp_client_mock` references anywhere on the Python test or source path).
- Records the two concrete breakages found and how the parallel agentic-fix run resolved them (orphaned `test_tool_integration_patterns`; leaked `mock_enhanced_mcp_client`/`mock_mcp_*` fixtures + `test_scenarios.py` MCP mocks).
- Establishes the **audit checklist** (collection + hermetic run + e2e-guard integrity) as a standing task list so any future slim-refactor re-runs it instead of trusting a cached "green".
- **No generated TypeScript** is touched and no B10/B11 contract bodies are authored in Python — this is a Python-floor audit only (B13).

## Capabilities
### New Capabilities
- `audit-integrity`: A standing loop-audit capability. After any large Python trans-file refactor (dead-code removal, MCP/feature excision), the agent MUST (a) collect every test module (unit + integration) with no `ImportError`, (b) run the hermetic unit suite to 100% pass, (c) confirm the 3 standing e2e guards (`ticket20`/`ticket22`/`greetings`) and their B5/B6 committed-baseline guard are intact, and (d) grep the whole `agents/agentics` tree for dangling symbols removed by the refactor. The audit outcome must be recorded in `agent-wiki/` and tracked as OpenSpec tasks before the change is declared done.

## Impact
- Affected code: `agents/agentics/src/*` (post-MCP-removal), `agents/agentics/tests/**` (conftest fixtures, `test_scenarios.py`, `test_langchain_best_practices.py`).
- Affected systems: `make test-agents-unit-mock`, `make loop-unit`, `make loop-e2e`, the `b5_committed_baseline_guard` fixture.
- Cross-references: `e2e-conftest-b5-guard` (prior B5/B6 audit), `python-agentic-slim-refactor` (the refactor under audit here), `agentic-tests-real-logic` + B18 (real-unit-gate reporting discipline).
