## 1. Create the spec
- [x] 1.1 Create `specs/llama-host-agnostic-rename/spec.md` with requirements for the rename
- [x] 1.2 `openspec validate llama-host-agnostic-rename` passes

## 2. Rename OLLAMA_* → LLAMA_* in source code (Python)
- [x] 2.1 `agents/agentics/src/clients.py`: rename module-level constants and env var reads
- [x] 2.2 `agents/agentics/src/config.py`: rename env var names in Config dataclass
- [x] 2.3 `agents/agentics/tests/unit/conftest.py`: rename env var defaults
- [x] 2.4 `agents/agentics/tests/unit/test_config_unit.py`: rename all OLLAMA refs
- [x] 2.5 `agents/agentics/tests/integration/conftest.py`: rename env var defaults
- [x] 2.6 `agents/agentics/tests/integration/_e2e_helpers.py`: rename env var reads
- [x] 2.7 `agents/agentics/tests/integration/test_agentics_app_integration.py`: rename all OLLAMA refs
- [x] 2.8 `agents/agentics/tests/integration/test_agents_integration.py`: rename env var reads
- [x] 2.9 `agents/agentics/tests/integration/test_configuration_integration.py`: rename env var refs
- [x] 2.10 `agents/agentics/tests/fixtures/mock_refactored_components.py`: rename env var mock data
- [x] 2.11 `agents/agentics/src/services.py`: rename OllamaClient → LlamaClient, OllamaError → LlamaError
- [x] 2.12 `agents/agentics/src/exceptions.py`: rename OllamaError → LlamaError
- [x] 2.13 `agents/agentics/src/agentics.py`: rename Ollama references in comments and error messages
- [x] 2.14 `agents/agentics/tests/unit/test_services_unit.py`: rename OllamaClient → LlamaClient, OllamaError → LlamaError
- [x] 2.15 `agents/agentics/tests/unit/test_exceptions_unit.py`: rename OllamaError → LlamaError
- [x] 2.16 `agents/agentics/tests/unit/test_agents_unit.py`: rename OllamaClient → LlamaClient
- [x] 2.17 `agents/agentics/tests/unit/test_implementation_planner_agent_unit.py`: rename Ollama → llama in comments
- [x] 2.18 `agents/agentics/tests/unit/test_agentics_app_unit.py`: rename Ollama → llama in comments
- [x] 2.19 `agents/agentics/tests/unit/test_slim_refactor_invariants_unit.py`: rename Ollama → llama in comments
- [x] 2.20 `agents/agentics/tests/unit/test_integrator_merge_unit.py`: rename Ollama → llama in comments
- [x] 2.21 `agents/agentics/tests/unit/test_enforce_task_completion_unit.py`: rename Ollama → llama in comments
- [x] 2.22 `agents/agentics/tests/integration/test_base64_e2e_integration.py`: rename Ollama → llama in comments
- [x] 2.23 `agents/agentics/tests/fixtures/mock_llm_responses.py`: rename "Ollama server" → "llama server"
- [x] 2.24 `agents/agentics/fix_integration_tests.py`: rename Ollama → llama in comments/docstrings

## 3. Rename in Makefile and compose files
- [x] 3.1 `Makefile`: OLLAMA_* → LLAMA_* already applied in prior change (docker-make-no-dagger)
- [x] 3.2 `Makefile`: `check-ollama` → `check-llama` already applied in prior change (macos-makefile-simplification)
- [x] 3.3 `Makefile`: echo message and docker_run command env vars already applied
- [x] 3.4 `docker-compose-files/agents.yaml`: OLLAMA_* → LLAMA_* already applied in prior change (llama-host-agnostic-routing)

## 4. Rename in documentation
- [x] 4.1 `README.md`: already verified clean (no OLLAMA refs)
- [x] 4.2 `AGENTS.md`: already verified clean (no OLLAMA refs)
- [x] 4.3 `docs/openspec-engineering-loop-harness.md`: already verified clean
- [x] 4.4 `docs/AGENTIC_ARCHITECTURE.md`: already verified clean
- [x] 4.5 `docs/architecture/INTEGRATION_TEST_PLAN.md`: already verified clean
- [x] 4.6 `CHANGELOG.md`: already verified clean
- [x] 4.7 `hermes/skills/openspec-loop-harness.md`: already verified clean
- [x] 4.8 `agent-wiki/2026-07-14-e2e-conftest-b5-guard.md`: already verified clean
- [x] 4.9 `scripts/validate-makefile/validate_makefile.py`: already verified clean
- [x] 4.10 `scripts/check-docs-sync.py`: rename Ollama → llama in comments
- [x] 4.11 `scripts/run-loop-harness.sh`: rename Ollama → llama in comments
- [x] 4.12 `scripts/ts_test_floor.sh`: rename Ollama → llama in comments
- [x] 4.13 All other docs/agent-wiki: verified clean (no OLLAMA refs in non-fixture/non-archive files)

## 5. Update OpenSpec specs (living specs, not archived changes)
- [x] 5.1 `openspec/specs/agentic-tests-real-logic/spec.md`: already verified clean
- [x] 5.2 `openspec/specs/integration-tests-lifecycle/spec.md`: already verified clean
- [x] 5.3 `openspec/specs/readme-docs/spec.md`: already verified clean

## 6. Update archived change records (historical accuracy)
- [x] 6.1 Archived changes intentionally left as-is for historical accuracy (B15 — archived changes are immutable records)

## 7. Verify
- [x] 7.1 `openspec validate llama-host-agnostic-rename` passes
- [x] 7.2 `grep -r OLLAMA` finds zero matches in source (excluding fixtures and .venv)
- [x] 7.3 `make test-agents-unit-mock` passes (525/525 green)
  - Fixed 4 TestLlamaClient failures in `test_services_unit.py`:
    - `test_llama_client_initialization_success`: captured `mock_ollama` from `patch` context instead of using stale imported `OllamaLLM` class
    - `test_llama_client_health_check_success`: removed `asyncio.Future()` from patch setup (was called before event loop existed); simplified to rely on `asyncio.run()` creating its own loop
    - `test_llama_client_is_available` / `invoke_success` / `invoke_not_available`: moved `OllamaLLM` patch inside each test's `with` block, trigger `client.client` explicitly before assertions
    - `test_llama_client_invoke_not_available`: fixed double-escaped regex `\\\\\\(test-model\\\\\\)` → raw string `r"llama service \(test-model\) is not available"`
- [x] 7.4 `make test-app` passes
- [x] 7.5 `make check-docs-sync` passes
- [x] 7.6 All Python source + test files verified clean (LlamaClient/LlamaError properly renamed)
