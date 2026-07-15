# docker-make-pipeline Specification

## Purpose
TBD - created by archiving change docker-make-no-dagger. Update Purpose after archive.
## Requirements
### Requirement: No Dagger references
The Makefile MUST NOT reference Dagger (`dagger.json`, `dagger-pipeline/`, `bin/dagger`, `$(DAGGER)`, `ensure-dagger-ready`, engine start/stop).

#### Scenario: No Dagger references
- **WHEN** the repository is grepped for Dagger
- **THEN** `grep -rni dagger Makefile docker-compose-files` returns nothing.

### Requirement: Build and test via compose
`make build-app` and `make test-app` MUST run the npm build/test inside the `tools.yaml` `app` compose service.

#### Scenario: Build via compose
- **WHEN** `make build-app` is run with no `bin/dagger` present
- **THEN** it runs `docker compose -f docker-compose-files/tools.yaml run --rm app npm run build` and exits 0.

### Requirement: Local agentic run
`make run-agentics CHANGE=<name>` MUST run the agentic pipeline inside the `agents.yaml` `agentics` service (no GitHub fetch, no MCP).

#### Scenario: Local agentic run
- **WHEN** `make run-agentics CHANGE=uuid-modal-agentic-generation` runs
- **THEN** it completes and writes `src/main.ts` / `src/__tests__/main.test.ts` without any Dagger or MCP process.

### Requirement: Agentic tests via compose
All agentic unit/integration test targets MUST run via `docker compose run` of the `agents.yaml` test services.

#### Scenario: Tests via compose
- **WHEN** `make test-agents-unit-mock` / `make test-agents-integration` run
- **THEN** they invoke the `agents.yaml` test services with no Dagger.

### Requirement: No MCP
`MCP_SERVER_URL` and the `mcp-bridge` service MUST be absent from the Makefile and `docker-compose-files/`.

#### Scenario: No MCP references
- **WHEN** the repo is grepped for MCP
- **THEN** `grep -rni MCP_SERVER_URL Makefile docker-compose-files` returns nothing and `docker-files/mcp/` is deleted.

### Requirement: Full pipeline without Dagger
`make test` (app + agents) and `make lint-python` MUST pass using only `docker compose` — no Dagger engine reachable.

#### Scenario: Full pipeline without Dagger
- **WHEN** `bin/dagger` is removed and `make test` / `make lint-python` run
- **THEN** both succeed via compose.

