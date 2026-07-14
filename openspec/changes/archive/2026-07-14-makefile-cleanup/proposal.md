## Why

The root `Makefile` has accumulated developer-only convenience targets that are not
part of the actual OpenSpec loop gate (generate → build-app → test-app →
`verify-agentics-after-run`). Specifically:

- `test-agents-unit-watch`, `test-agents-integration-watch` (watchmedo auto-restart)
  — dev-only, never used by the loop; introduce a heavy `watchmedo` dependency.
- `test-agents-unit-verbose`, `test-agents-integration-verbose`,
  `test-agents-unit-fail-verbose`, `test-agents-integration-fail-verbose` — thin
  `-v`/`--last-failed` wrappers that overlap with `test-agents-unit`/`test-agents-integration`.
- `validate-test-suite` Makefile target + the `validate-test-suite` compose **service**
  (`docker-compose-files/agents.yaml`) — runs `scripts/test_suite_validation.py`, a
  hardcoded fake-`Calculator` smoke test that never validates the real generated TS. Its
  only genuine value is proving the `test_suite` Python module still imports/runs, which
  belongs as a real unit test, not a separate compose service + Makefile gate.

These add noise, extra compose services, and a misleading "validation" step that does not
validate the loop's actual output. Removing them leaves a cleaner, loop-focused Makefile
and compose file.

## What Changes

- `Makefile`: remove `*-watch`, `*-verbose`, `*-fail-verbose` targets and drop them from
  the `.PHONY` list. Remove the `validate-test-suite` target. `test-agents` /
  `test-agents-real` / `verify-agentics-after-run` keep unit + integration only.
- `docker-compose-files/agents.yaml`: remove the `validate-test-suite` **service** entirely
  (it is the only consumer of `scripts/test_suite_validation.py`).
- Coverage preserved: convert the `validate-test-suite` check into a **real unit test**
  (`test_test_suite_unit.py`) that imports `test_suite.validate_llm_test_suite` and
  `generate_test_suite_report` and asserts on the result structure — no hardcoded example.
  This runs inside `test-agents-unit`, so coverage is retained without a separate service.
- `scripts/test_suite_validation.py` may be deleted once the unit test replaces it.

## Capabilities

### New Capabilities
- `makefile-cleanup`: The Makefile exposes only loop-relevant targets; all watch/verbose
  convenience targets and the standalone `validate-test-suite` gate (Makefile target +
  compose service) are removed, with equivalent coverage retained as a real unit test.

### Modified Capabilities
- `docker-make-no-dagger`: the compose file no longer defines a `validate-test-suite`
  service; the loop gate is `run-agentics` → `build-app` → `test-app` →
  `verify-agentics-after-run` (unit + integration).

## Impact

- `Makefile`: fewer targets; `.PHONY` trimmed.
- `docker-compose-files/agents.yaml`: one fewer service (smaller image/build surface).
- `agents/agentics/tests/unit/test_test_suite_unit.py`: new real unit test (replaces the
  script's smoke check).
- `scripts/test_suite_validation.py`: removed (superseded by the unit test).
