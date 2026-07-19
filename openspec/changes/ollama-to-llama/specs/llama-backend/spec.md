## ADDED Requirements
### Requirement: Agentic pipeline uses llama.cpp server
The system MUST use `langchain-openai` and `openai` Python packages to communicate with the LLM server running on the host via OpenAI-compatible API at `http://localhost:11434/v1/chat/completions`.

#### Scenario: Dependencies are correct
- **WHEN** `pip install` runs in the agentics container
- **THEN** `langchain-openai` and `openai` are installed, and `langchain-ollama` and `ollama` are absent.

#### Scenario: Config uses llama env vars
- **WHEN** `AgenticsConfig` initializes from environment
- **THEN** it reads `LLAMA_HOST`, `LLAMA_REASONING_MODEL`, `LLAMA_CODE_MODEL` env vars.

#### Scenario: LlamaClient works correctly
- **WHEN** `LlamaClient.invoke()` is called
- **THEN** it sends a request to the OpenAI-compatible API and returns the response text.

### Requirement: All code references renamed
All references to `ollama` in code, config, env vars, Makefile targets, and comments MUST be renamed to `llama`.

#### Scenario: No ollama references remain in source
- **WHEN** `grep -r 'ollama' agents/agentics/src/` runs
- **THEN** no matches are found.

#### Scenario: No ollama references remain in tests
- **WHEN** `grep -r 'ollama' agents/agentics/tests/` runs
- **THEN** no matches are found (except in test data fixtures that explicitly test backward compatibility).

#### Scenario: Makefile uses llama env vars
- **WHEN** `make` is invoked
- **THEN** `LLAMA_HOST`, `LLAMA_REASONING_MODEL`, `LLAMA_CODE_MODEL` are used instead of `OLLAMA_*` vars.

### Requirement: Tests pass after refactor
- The system SHALL maintain test pass rates after the refactor.
- The system MUST pass `make test-agents-unit-mock` with the same passing count as before the refactor.

#### Scenario: Unit tests pass
- **WHEN** `pytest tests/unit/` runs
- **THEN** all previously-passing tests still pass.

#### Scenario: Integration tests pass (mocked)
- **WHEN** `pytest tests/integration/` runs with mocked LLM calls
- **THEN** all previously-passing tests still pass.

### Requirement: Backwards-compatible env var aliases
- The system SHALL read old `OLLAMA_HOST` env var as a fallback alias when `LLAMA_HOST` is not set, to preserve backwards compatibility.

#### Scenario: Legacy env var still works
- **WHEN** `OLLAMA_HOST` is set but `LLAMA_HOST` is not
- **THEN** `AgenticsConfig` uses the `OLLAMA_HOST` value.

### Requirement: Docker compose env vars updated
- The system SHALL pass `LLAMA_HOST`, `LLAMA_REASONING_MODEL`, `LLAMA_CODE_MODEL` env vars to containers in `docker-compose-files/agents.yaml`.

#### Scenario: Compose passes llama env vars
- **WHEN** `docker compose -f docker-compose-files/agents.yaml` runs
- **THEN** all agentics services receive `LLAMA_HOST`, `LLAMA_REASONING_MODEL`, `LLAMA_CODE_MODEL` environment variables.
