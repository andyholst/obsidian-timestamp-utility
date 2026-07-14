# Design — makefile-cleanup

## Targets to remove
- `test-agents-unit-watch` / `test-agents-integration-watch`: `watchmedo auto-restart`
  dev-loop wrappers. Not used by the loop; drop the targets + `.PHONY` entries.
- `test-agents-unit-verbose` / `test-agents-integration-verbose` / `*-fail-verbose`:
  thin `-v` / `--last-failed` wrappers over the base targets. Drop; the base targets
  already support `TEST_FILTER` and verbose can be passed ad hoc.
- `validate-test-suite` (Makefile): runs the `validate-test-suite` compose service. Remove.

## Compose change
- `docker-compose-files/agents.yaml`: delete the `validate-test-suite` service block
  (lines ~86-105). It is the only consumer of `scripts/test_suite_validation.py`.

## Coverage preservation
- Add `agents/agentics/tests/unit/test_test_suite_unit.py` that:
  - imports `from test_suite import validate_llm_test_suite, generate_test_suite_report`,
  - runs `validate_llm_test_suite` on a sample (loaded from a fixture, not a hardcoded
    inline string in the script) and asserts `overall_score`/`risk_level`/etc. exist,
  - runs `generate_test_suite_report` and asserts a non-trivial string.
- This runs inside `test-agents-unit`, so the `test_suite` module stays covered without a
  dedicated service.
- Delete `scripts/test_suite_validation.py` after the unit test lands.

## Verification
- `make -n test-agents-unit-watch` → "No rule to make target".
- `docker compose -f docker-compose-files/agents.yaml config | grep validate-test-suite` → empty.
- `make test-agents-real` passes (unit covers `test_suite`).
