## ADDED Requirements

### Requirement: Integration tests are a mandatory loop phase
The system MUST run the integration test suite as an explicit, ordered step of the loop-harness
(`make loop-integration`), positioned between the e2e gate and the `build-app` gate.

#### Scenario: loop-harness includes integration
- **WHEN** `make loop-harness` is invoked
- **THEN** it executes `loop-unit` → `loop-e2e` → `loop-integration` → `loop-build-app` → `loop-test-app` in that order, and fails closed if any step is non-zero.

### Requirement: No dead integration tests
The system MUST NOT retain duplicate or obsolete integration test files. When a test file is a
strict duplicate of another (or superseded by a canonical per-agent file), the duplicate MUST be deleted.

#### Scenario: dead duplicate deleted
- **WHEN** an inventory finds `test_jest_execution_integration_fixed.py` / `test_jest_execution_minimal.py` duplicating `test_jest_execution_integration.py`
- **THEN** the duplicates are removed and the canonical file retains the assertions.

### Requirement: Live tests skip cleanly without credentials
Any integration test that requires `GITHUB_TOKEN` or a live Ollama endpoint (`OLLAMA_HOST`) MUST
skip cleanly (not error) when that dependency is absent, so `make loop-integration` is green on a
machine without network credentials.

#### Scenario: no token, no failure
- **WHEN** `make loop-integration` runs without `GITHUB_TOKEN` set
- **THEN** GitHub-dependent tests are skipped and the suite exits 0 with a recorded skip count.

### Requirement: Categorization is documented
The agent MUST produce + keep a categorization of the integration suite (hermetic / live-Ollama /
live-GitHub / dead) and reflect it in this change's `tasks.md` so "the integration tests work and
are updated" is provable, not asserted.

#### Scenario: audit recorded
- **WHEN** the inventory is complete
- **THEN** each file is listed with its category and the action taken (keep / hermeticize / delete).
