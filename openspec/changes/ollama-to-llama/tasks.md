# Tasks: ollama-to-llama

## 1. Dependency manifests
1.1 Update `docker-files/pip-requirements/requirements.in`: `langchain-ollama` → `langchain-openai`, remove `ollama`, add `openai`
1.2 Regenerate `agents/agentics/requirements.txt` via `make generate-requirements`
1.3 Update `agents/agentics/pyproject.toml`: `langchain-ollama` → `langchain-openai`, add `openai`

## 2. Core source files
2.1 `agents/agentics/src/exceptions.py`: `OllamaError` → `LlamaError` (rename class, update docstring)
2.2 `agents/agentics/src/config.py`: rename `ollama_host` → `llama_host`, `ollama_reasoning_model` → `llama_reasoning_model`, `ollama_code_model` → `llama_code_model`; add backwards-compatible aliases; rename validator
2.3 `agents/agentics/src/services.py`: `OllamaClient` → `LlamaClient`; `OllamaLLM` → `OpenAI`; update imports, client name, health check, invoke method

## 3. Agentics source files (all imports)
3.1 Find and replace all `from langchain_ollama import OllamaLLM` → `from langchain_openai import ChatOpenAI`
3.2 Find and replace all `OllamaClient` → `LlamaClient` in source
3.3 Find and replace all `OllamaError` → `LlamaError` in source
3.4 Find and replace all `config.ollama_*` → `config.llama_*` in source

## 4. Test files and fixtures
4.1 `agents/agentics/tests/unit/conftest.py`: env vars, config field names
4.2 `agents/agentics/tests/unit/test_config_unit.py`: all `ollama_*` field references
4.3 `agents/agentics/tests/unit/test_agentics_app_unit.py`: `ollama_host`, `ollama_*_model`, service manager fields
4.4 `agents/agentics/tests/unit/test_code_generator_agent_unit.py`: `OllamaLLM` import
4.5 `agents/agentics/tests/unit/test_agents_unit.py`: `mock_ollama` → `mock_llm`
4.6 `agents/agentics/tests/unit/test_langchain_best_practices.py`: comments
4.7 Update fixture files: mock_llm_responses.py, mock_refactored_components.py
4.8 `agents/agentics/fix_integration_tests.py`: `OllamaLLM` → `ChatOpenAI`

## 5. Makefile and shell scripts
5.1 Makefile: `OLLAMA_*` env vars → `LLAMA_*`, `check-ollama` target → `check-llama`
5.2 `scripts/run-loop-harness.sh`: Ollama comments → llama comments

## 6. Docker compose
6.1 `docker-compose-files/agents.yaml`: env vars `OLLAMA_*` → `LLAMA_*`, comments

## 7. AGENTS.md
7.1 Replace Ollama references with llama references throughout

## 8. Verification
8.1 Run `make test-agents-unit-mock` to verify tests pass
8.2 Run `make test-agents-integration-mock` if applicable
8.3 Run `make lint-python` to verify no lint errors
8.4 Run `make format` to ensure formatting is correct
