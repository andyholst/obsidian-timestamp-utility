# Design: docker-make-no-dagger

## Mapping of old Dagger targets → docker compose

| Old (Dagger) | New (compose) |
|---|---|
| `build-app` → `$(DAGGER) call -m dagger-pipeline build-app` | `docker compose -f docker-compose-files/tools.yaml run --rm app npm run build` |
| `test-app` → `$(DAGGER) call -m dagger-pipeline test-app` | `docker compose -f docker-compose-files/tools.yaml run --rm app npm test` |
| `lint-python` → `$(DAGGER) call -m dagger-pipeline lint-python` | `docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents ruff .` (or local `ruff`) |
| `run-agentics` → Dagger-gated python | `docker compose -f docker-compose-files/agents.yaml run --rm agentics` (runs `python -m prod.agentics openspec:<CHANGE>`) |
| `test-agents-unit-mock` | `docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents` |
| `test-agents-integration` | `docker compose -f docker-compose-files/agents.yaml run --rm integration-test-agents` |
| `validate-test_suite` | `docker compose -f docker-compose-files/agents.yaml run --rm validate-test-suite` |

## Removal list

- `dagger.json`, `dagger-pipeline/` (whole dir), `bin/dagger`.
- Makefile variables: `DAGGER`, `DAGGER_ENGINE_HOST`, `DAGGER_ENGINE_PORT`, `SOCAT_PORT`,
  `OLLAMA_LOCAL_PORT`, `HOST_IP`, `OLLAMA_HOST` (Dagger-container proxy) — keep a plain
  `OLLAMA_HOST=http://localhost:11434` for the agentics service.
- Makefile targets: `install-dagger`, `sync-pipeline-deps`, `generate-sdk`,
  `ensure-dagger-ready`, `start-engine`, `stop-engine`, `check-engine`, `start-socat`,
  `stop-socat`, `check-mcp`, `start-mcp`, `stop-mcp`, `start-mcp-persist`,
  `stop-mcp-persist`, `generate-requirements`, `dagger-clean`, `clean-dagger-cache`,
  `clean-dagger-engine`, `nuke-dagger`, `kill-dagger-shims`, `rm-stale-dagger-dirs`.
- `docker-files/mcp/` and the `mcp-bridge` service in `agents.yaml`.

## Note on compose runtime

Compose must target whatever OCI runtime is present. The Makefile already computes
`DOCKER_SOCK`; we keep that detection and pass it through `docker compose` (which
auto-discovers the socket). No Dagger engine binary is started.
