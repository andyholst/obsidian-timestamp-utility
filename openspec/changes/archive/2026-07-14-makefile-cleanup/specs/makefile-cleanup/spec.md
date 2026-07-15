# Capability: makefile-cleanup

The Makefile and agents compose file expose only loop-relevant targets; watch/verbose
convenience targets and the standalone `validate-test-suite` gate are removed, with
equivalent coverage retained as a real unit test.

## ADDED Requirements

### Requirement: Remove watch and verbose convenience targets
The Makefile MUST NOT define `*-watch`, `*-verbose`, or `*-fail-verbose` targets, and they
MUST be absent from `.PHONY`. The loop uses only `test-agents-unit`, `test-agents-integration`,
`test-agents`, `test-agents-real`, `verify-agentics-after-run`, `build-app`, `test-app`,
`run-agentics`, `lint-python`.

#### Scenario: Watch/verbose targets are gone
- **WHEN** a developer runs `make -n <watch-or-verbose-target>`
- **THEN** make reports "No rule to make target" (the target does not exist).

### Requirement: Remove standalone validate-test-suite gate
The `validate-test-suite` Makefile target MUST be removed, and the `validate-test-suite`
**service** MUST be removed from `docker-compose-files/agents.yaml`.

#### Scenario: validate-test-suite service removed
- **WHEN** `docker compose -f docker-compose-files/agents.yaml config` is evaluated
- **THEN** no `validate-test-suite` service is present.

### Requirement: Equivalent coverage retained as a real unit test
The `validate-test-suite` smoke check MUST be replaced by a real unit test
`agents/agentics/tests/unit/test_test_suite_unit.py` that imports
`test_suite.validate_llm_test_suite` and `generate_test_suite_report` and asserts on the
result structure (no hardcoded fake `Calculator` example). `scripts/test_suite_validation.py`
MAY be deleted once the unit test exists.

#### Scenario: test_suite module covered by a real unit test
- **WHEN** `make test-agents-unit` runs
- **THEN** the `test_test_suite_unit.py` test passes, exercising the real `test_suite` module.

## ADDED Acceptance Criteria

- `make test-agents` and `verify-agentics-after-run` pass with no `validate-test-suite` dependency.
- `docker compose -f docker-compose-files/agents.yaml config` shows no `validate-test-suite` service.
- `agents/agentics/tests/unit/test_test_suite_unit.py` exists and passes.
- `scripts/test_suite_validation.py` removed (or superseded).
