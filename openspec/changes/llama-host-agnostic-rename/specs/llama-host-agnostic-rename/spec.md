# Capability: llama-host-agnostic-rename

Rename `OLLAMA_*` environment variables to `LLAMA_*` across the entire codebase, and make the compose files host-agnostic so they work on Linux (Docker/nerdctl) and macOS (Docker Desktop/colima) without platform-specific hardcoded hostnames.

## ADDED Requirements

### Requirement: No OLLAMA env var names in source
The codebase MUST NOT use `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_CODE_MODEL`, `OLLAMA_REASONING_MODEL`, or `OLLAMA_TIMEOUT` environment variable names in any source file, Makefile, or compose file (excluding test fixtures and archived changelogs).

#### Scenario: No OLLAMA env vars in source
- **WHEN** the repository is searched for `OLLAMA_` in source files (excluding `tests/fixtures/` and `.venv/`)
- **THEN** zero matches are found.

#### Scenario: LLAMA env vars present
- **WHEN** the repository is searched for `LLAMA_` in source files
- **THEN** the following variables are found: `LLAMA_HOST`, `LLAMA_MODEL`, `LLAMA_CODE_MODEL`, `LLAMA_REASONING_MODEL`, `LLAMA_TIMEOUT`.

### Requirement: Makefile uses LLAMA variables
The Makefile MUST use `LLAMA_HOST`, `LLAMA_MODEL`, `LLAMA_CODE_MODEL`, and `LLAMA_TIMEOUT` variables instead of OLLAMA equivalents.

#### Scenario: Makefile defines LLAMA variables
- **WHEN** the Makefile is parsed
- **THEN** it defines `LLAMA_MODEL`, `LLAMA_CODE_MODEL`, `LLAMA_HOST`, and `LLAMA_TIMEOUT` with `?= ` defaults.

### Requirement: Compose files use LLAMA variables
The docker-compose files MUST use `LLAMA_*` environment variable names instead of `OLLAMA_*`.

#### Scenario: agents.yaml uses LLAMA_HOST
- **WHEN** `docker-compose-files/agents.yaml` is parsed
- **THEN** it uses `LLAMA_HOST` environment variable (not hardcoded hostnames).

### Requirement: Compose files are host-agnostic
The compose files MUST NOT hardcode platform-specific hostnames (`host.lima.internal`, `host.docker.internal`). They MUST rely on the Makefile-provided `LLAMA_HOST` variable.

#### Scenario: No hardcoded hostnames in agents.yaml
- **WHEN** `docker-compose-files/agents.yaml` is searched for `host.lima.internal` or `host.docker.internal`
- **THEN** no matches are found.

### Requirement: check-llama target uses /health endpoint
The Makefile MUST have a `check-llama` target (renamed from `check-ollama`) that checks the `/health` endpoint of the llama.cpp server, not the `/api/tags` endpoint.

#### Scenario: check-llama exists
- **WHEN** `make check-llama` is run
- **THEN** it curls `$(LLAMA_HOST)/health` and checks for HTTP 200.

#### Scenario: check-llama fails without server
- **WHEN** `make check-llama` is run without a llama server running
- **THEN** it exits with code 1 and prints an error message.

### Requirement: Python clients use LLAMA variables
The Python agentics source files MUST read `LLAMA_HOST`, `LLAMA_CODE_MODEL`, and `LLAMA_REASONING_MODEL` environment variables instead of `OLLAMA_*` equivalents.

#### Scenario: clients.py uses LLAMA_HOST
- **WHEN** `agents/agentics/src/clients.py` is parsed
- **THEN** it reads `os.getenv("LLAMA_HOST", ...)` and uses `LLAMA_CODE_MODEL`, `LLAMA_REASONING_MODEL`.

#### Scenario: config.py uses LLAMA variables
- **WHEN** `agents/agentics/src/config.py` is parsed
- **THEN** it reads `LLAMA_HOST`, `LLAMA_REASONING_MODEL`, `LLAMA_CODE_MODEL` from environment.

### Requirement: Tests use LLAMA variables
All test files in `agents/agentics/tests/` MUST use `LLAMA_*` environment variable names.

#### Scenario: integration conftest uses LLAMA
- **WHEN** `agents/agentics/tests/integration/conftest.py` is parsed
- **THEN** it uses `LLAMA_HOST`, `LLAMA_REASONING_MODEL`, `LLAMA_CODE_MODEL` defaults.

#### Scenario: unit test_config_unit uses LLAMA
- **WHEN** `agents/agentics/tests/unit/test_config_unit.py` is parsed
- **THEN** all references to OLLAMA env vars use LLAMA equivalents.

### Requirement: Documentation updated
All documentation files (README.md, AGENTS.md, docs/, hermes/skills/) MUST use `LLAMA_*` variable names and "llama" terminology instead of "Ollama".

#### Scenario: README uses LLAMA_HOST
- **WHEN** `README.md` is parsed
- **THEN** it documents `LLAMA_HOST` (not `OLLAMA_HOST`) and uses "llama" terminology.

### Requirement: Archived changes updated
Archived OpenSpec change records MUST be updated to reflect the rename for historical accuracy.

#### Scenario: Archived tasks use LLAMA
- **WHEN** any file in `openspec/changes/archive/` is searched for `OLLAMA_`
- **THEN** zero matches are found (all renamed to `LLAMA_`).

## ADDED Acceptance Criteria

- `grep -r OLLAMA --include=*.py --include=*.yaml --include=Makefile --exclude-dir=.venv --exclude-dir=tests/fixtures` returns zero matches
- `make test-agents-unit-mock` passes
- `make test-app` passes
- `make check-llama` works (or skips cleanly when no server is running)
- All documentation reflects `LLAMA_*` variable names
