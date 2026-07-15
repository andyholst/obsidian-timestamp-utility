# agentic-tests-real-logic Specification

## Purpose
TBD - created by archiving change agentic-tests-real-logic. Update Purpose after archive.
## Requirements
### Requirement: Post-run agentic verification gate
After `make run-agentics` completes, the pipeline (or the loop) MUST re-run `make test-agents-unit` AND `make test-agents-integration` (real, not mocked) to confirm the refactored Python agentic code is still valid and in sync with the generated TS.

#### Scenario: Agentic suite re-run after generation
- **WHEN** `make run-agentics CHANGE=<name>` finishes generating/refactoring the Python + TS
- **THEN** the unit and integration/e2e agentic tests are executed and MUST all pass before the change is considered done.

### Requirement: Unit tests exercise real logic (mock only external calls)
The agentic UNIT tests MUST test the REAL implementation of the Python modules
(state adapters, `openspec_loader.load_change`, `code_integrator` assembly,
`post_test_runner` parse/metrics, export_name derivation, prompt construction,
omission-guard comparison). Mocks MUST be used ONLY for **external calls**
(GitHub API, Ollama/LLM HTTP, network, filesystem boundaries) — never to replace
the unit under test. The deterministic behaviour of each module is asserted on
real return values / real state transitions.

#### Scenario: A deterministic unit is tested without mocking its logic
- **WHEN** a unit test for a deterministic function/class runs
- **THEN** it invokes the real implementation (not a MagicMock/stub of the unit itself) and asserts on real return values, while any GitHub/Ollama/network call inside it is mocked at the boundary only.

### Requirement: Integration/e2e tests make real calls
The agentic INTEGRATION and e2e tests MUST invoke the REAL Ollama endpoint
(`OLLAMA_HOST`) and, where the test exercises issue fetching, the REAL GitHub API
(with `GITHUB_TOKEN`) — NO `@patch` / `monkeypatch` / fake HTTP for those.
They must perform an end-to-end generation and assert on real generated TS output.

#### Scenario: e2e test hits real Ollama (and real GitHub when relevant)
- **WHEN** an integration/e2e test that exercises code generation runs
- **THEN** it makes a real request to `OLLAMA_HOST` (no patched LLM client) and,
  if it fetches an issue, a real GitHub call — and validates the real generated TypeScript.

### Requirement: Mocks only for non-runnable external boundaries
Mocks MAY be used ONLY for external boundaries that cannot run in CI (e.g. a network service that is genuinely unavailable), and the test MUST document WHY the mock is necessary.

#### Scenario: Mock justified and documented
- **WHEN** a test mocks an external boundary
- **THEN** the mock is accompanied by a comment/assertion explaining the boundary cannot run here, and a real-call test exists elsewhere (or is gated behind the integration/e2e marker).

### Requirement: Failure blocks the change
If the post-run agentic unit or integration/e2e suite fails, the change MUST NOT be considered done; the loop MUST report the failing agentic test honestly (same honesty rule as the TS self-correct loop).

#### Scenario: Agentic test failure reported
- **WHEN** the re-run agentic suite fails after `run-agentics`
- **THEN** the pipeline reports `agentic_tests_passed=False` with the failing test name, and does not claim the change is complete.

