## ADDED Requirements

### Requirement: Audit gate runs before declaring a slim-refactor green
The system MUST NOT declare a trans-file Python refactor "done"/"green" until an audit gate has run that collects every test module (unit + integration) with zero `ImportError`, runs the hermetic unit suite to 100% pass, and confirms the 3 standing e2e guards plus the B5/B6 committed-baseline guard are intact.

#### Scenario: Half-refactor leaves dangling references
- **WHEN** a refactor deletes a symbol (e.g. `src.agentics.mcp_tools`, `MCPClient`, `create_enhanced_mcp_client_mock`) from source/fixtures but leaves an import or usage elsewhere (conftest, a test body, `test_scenarios.py`)
- **THEN** the audit collects the test tree and the `ImportError` surfaces as a hard collection failure, and the agent MUST fix the dangling reference (delete the dead test/fixture or repoint it) rather than report "green".

### Requirement: No dangling symbols from a removed capability remain
The system MUST have zero references to a removed capability's symbols across `agents/agentics/src` and `agents/agentics/tests` after the refactor is complete (MCP removal → no `mcp_tools`, `MCPClient`, `MCPError`, `MCP_SERVER_URL`, `create_mcp_*`, `mock_mcp_*` anywhere outside intentional allowlists).

#### Scenario: Grep confirms removal completeness
- **WHEN** the audit greps the whole `agents/agentics` tree for the removed capability's symbol names
- **THEN** the only matches are in `__pycache__` byte-code or in intentional allowlisted locations (e.g. a deliberately-kept `src/__init__.py` re-export that still resolves), and every test/fixture import resolves.

### Requirement: Audit outcome is recorded and tasks are ticked as verified
The system MUST record the audit verdict in `agent-wiki/YYYY-MM-DD-<change>.md` and the change's `tasks.md`, ticking each checkbox only after the underlying check actually passed (B16 discipline).

#### Scenario: Findings tracked as OpenSpec tasks
- **WHEN** the audit finds a breakage or incomplete cleanup during a refactor
- **THEN** it is added as a concrete, verifiable task in this change's `tasks.md` (with the file + symbol), fixed, re-verified, and only then ticked — never left open, never silently dropped.
