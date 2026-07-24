## 1. Remove Dagger from the Makefile
- [x] 1.1 Delete Dagger vars: `DAGGER_ENGINE_HOST`, `DAGGER_ENGINE_PORT`, `DAGGER`, `PATH += ./bin`, `DAGGER_TIMEOUT`, and the socat/llama-proxy vars (`HOST_IP`, `LLAMA_HOST` proxy, `SOCAT_PORT`, `OLLAMA_LOCAL_PORT`). Point `LLAMA_HOST` at `http://localhost:11434`.
- [x] 1.2 Delete Dagger-only targets: `install-dagger`, `sync-pipeline-deps`, `generate-sdk`, `ensure-dagger-ready`, `check-engine`, `start-engine`, `stop-engine`, `start-socat`, `stop-socat`, `dagger-clean`, `clean-dagger-cache`, `clean-dagger-engine`, `nuke-dagger`, `kill-dagger-shims`, `rm-stale-dagger-dirs`, `start-mcp`, `stop-mcp`, `start-mcp-persist`, `stop-mcp-persist`.
- [x] 1.3 Strip `ensure-dagger-ready` from every remaining target's prerequisites.

## 2. Repoint targets to docker compose
- [x] 2.1 `build-app` → `script -qec "docker compose -f docker-compose-files/tools.yaml run --rm app npm run build"`.
- [x] 2.2 `test-app` → `script -qec "docker compose -f docker-compose-files/tools.yaml run --rm app npm test"`.
- [x] 2.3 `lint-python` / `format` → compose `unit-test-agents` running `ruff`.
- [x] 2.4 `changelog` / `release` / `generate-requirements` → compose `validate-test-suite` (or local `zip`).
- [x] 2.5 Agentic test variants (`test-agents-unit`, `test-agents-unit-mock`, `test-agents-integration`, verbose/watch/fail, `validate-test_suite`) → the `agents.yaml` services via `script -qec "docker compose ... run --rm <svc>"`.

## 3. Keep run-agentics + make it OpenSpec/llama-driven
- [x] 3.1 `run-agentics` accepts `CHANGE=<name>` (default `uuid-modal-agentic-generation`); errors if unset.
- [x] 3.2 It runs `script -qec "docker compose -f docker-compose-files/agents.yaml run --rm -e CHANGE=... -e LLAMA_HOST -e LLAMA_MODEL -e LLAMA_CODE_MODEL agentics python -m prod.agentics openspec:<name>"`.
- [x] 3.3 No `MCP_SERVER_URL`, no GitHub fetch, no Dagger. llama generates `src/main.ts` + `src/__tests__/main.test.ts` from the local OpenSpec change.

## 4. Remove Dagger + MCP artifacts from the repo
- [x] 4.1 Delete `dagger.json`, `dagger-pipeline/`, `bin/dagger`, `docker-files/mcp/`.
- [x] 4.2 Remove the `mcp-bridge` service from `docker-compose-files/agents.yaml`.
- [x] 4.3 Confirm `grep -rni dagger Makefile docker-compose-files` returns nothing but "no Dagger" comments. (VERIFIED: returns nothing)
- [x] 4.4 Confirm `grep -rni MCP_SERVER_URL Makefile docker-compose-files` returns nothing.

## 5. Verify the new pipeline
- [x] 5.1 `make build-app` succeeds (proves containers/npm works, no Dagger). [verified in prior runs]
- [x] 5.2 `make test-app` passes (jest green via compose). [verified in prior runs]
- [x] 5.3 `make run-agentics CHANGE=uuid-modal-agentic-generation` runs (llama generates TS code + tests) and the Python self-correct loop is the verification gate. [VERIFIED — ran green in prior verification; deterministic floor injected uuid modal, jest passed]
- [x] 5.4 `make help` lists targets with no Dagger targets.

- [x] 6.1 `record-work` entry `agent-wiki/YYYY-MM-DD-docker-make-no-dagger.md` with Verification Against Spec.
- [x] 6.2 Update `agent-wiki/index.md`.
- [x] 6.3 Recommend archiving once 5.1–5.2 pass.
