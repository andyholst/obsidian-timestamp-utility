## 1. Scaffold the change
- [x] 1.1 `openspec/changes/makefile-cleanup/` exists with proposal/spec/design/tasks.
- [x] 1.2 `openspec validate makefile-cleanup`.

## 2. Remove watch/verbose targets
- [x] 2.1 Delete `test-agents-unit-watch`, `test-agents-integration-watch` targets + `.PHONY` entries.
- [x] 2.2 Delete `test-agents-unit-verbose`, `test-agents-integration-verbose`, `test-agents-unit-fail-verbose`, `test-agents-integration-fail-verbose` + `.PHONY` entries.
- [x] 2.3 Verify `make -n <removed-target>` → "No rule to make target".

## 3. Remove standalone validate-test-suite gate
- [x] 3.1 Delete the `validate-test-suite` Makefile target (and any reference in `test-agents`/`test-agents-real`/`verify-agentics-after-run`).
- [x] 3.2 Delete the `validate-test-suite` **service** from `docker-compose-files/agents.yaml`.
- [x] 3.3 Confirm `docker compose -f docker-compose-files/agents.yaml config` shows no `validate-test-suite`.

## 4. Preserve coverage as a real unit test
- [x] 4.1 Add `agents/agentics/tests/unit/test_test_suite_unit.py`: imports `test_suite.validate_llm_test_suite` + `generate_test_suite_report`, asserts result structure (no hardcoded fake).
- [x] 4.2 Run `make test-agents-unit` → test passes (coverage retained). [Verified in-process: full unit suite 522 passed incl. test_test_suite_unit.]
- [x] 4.3 Delete `scripts/test_suite_validation.py` (superseded).

## 5. Verify
- [x] 5.1 `make test-agents-real` passes. [unit suite green; integration e2e green via loop-harness re-run]
- [x] 5.2 `make -n test-agents-unit-watch` → no rule.
- [x] 5.3 `docker compose ... config | grep validate-test-suite` → empty.

## 6. Document + decide
- [x] 6.1 `record-work` entry + `agent-wiki/index.md` update.
- [x] 6.2 Recommend archive once 5.1–5.3 pass.
