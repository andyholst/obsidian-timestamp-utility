## Why

Every build/test/lint/Makefile target was gated behind `ensure-dagger-ready`, which
installs and starts a **Dagger engine** (`bin/dagger`). This makes local dev and CI
slow, heavy, and fragile, and fails in daemon-less/nerdctl hosts. We already have
`docker-compose-files/` + a new `containers/` layout (one Dockerfile per container).
The fix: **remove Dagger entirely**; route every Makefile target through `docker compose
run` (or direct `npx`/`ruff` where sensible). The agentic pipeline (`run-agentics`) keeps
running, now driven by a `CHANGE=<openspec-change>` argument that reads the local
OpenSpec tasks and uses **llama** to generate the TS code and TS tests. MCP is dropped
(confirmed unnecessary — the agentic code writes files via `PROJECT_ROOT`).

## What Changes

- Remove `dagger.json`, `dagger-pipeline/` (Dagger SDK module), `bin/dagger`, and the
  `PATH += ./bin` / Dagger engine env vars from the Makefile.
- Delete all Dagger-only Makefile targets: `install-dagger`, `sync-pipeline-deps`,
  `generate-sdk`, `ensure-dagger-ready`, `check-engine`, `start-engine`, `stop-engine`,
  `start-socat`, `stop-socat`, `dagger-clean`, `clean-dagger-cache`, `clean-dagger-engine`,
  `nuke-dagger`, `kill-dagger-shims`, `rm-stale-dagger-dirs`, `start-mcp`, `stop-mcp`,
  `start-mcp-persist`, `stop-mcp-persist`, and the socat/llama-proxy vars.
- Replace every `$(DAGGER) call -m dagger-pipeline <op>` with
  `docker compose -f docker-compose-files/<svc>.yaml run --rm <service>` (wrapped in
  `script -qec` for nerdctl TTY compatibility).
- Keep `run-agentics` and the agentic test variants (`test-agents-unit`,
  `test-agents-unit-mock`, `test-agents-integration`, verbose/watch/fail variants,
  `validate-test_suite`) — all executed through docker compose.
- `run-agentics` takes `CHANGE=<name>`: it runs `python -m prod.agentics openspec:<name>`,
  which ingests `openspec/changes/<name>/{proposal.md,tasks.md,specs/**}` locally and uses
  **llama** (`LLAMA_HOST`, `LLAMA_MODEL`) to generate `src/main.ts` + `src/__tests__/main.test.ts`.
- Drop MCP: no `mcp-bridge` service, no `MCP_SERVER_URL` anywhere.

## Capabilities

### New Capabilities
- `docker-make-pipeline`: All build/test/lint/agentic Makefile targets run via
  `docker compose run` against `docker-compose-files/*.yaml` + `containers/`, with **no
  Dagger** and **no MCP**. `run-agentics CHANGE=<name>` generates TS via llama from the
  local OpenSpec change.

### Modified Capabilities
<!-- No plugin spec-level behavior changes; this is build/CI infra. -->

## Impact

- Build/CI infra: Makefile, `docker-compose-files/*`, `containers/*`, `dagger.json`,
  `dagger-pipeline/`, `bin/`, `docker-files/mcp/`.
- Runtime: developers need Docker/nerdctl instead of a Dagger engine. Works on daemon-less
  hosts (nerdctl/containerd) since compose targets the socket.
- The companion change `uuid-modal-agentic-generation` exercises `run-agentics CHANGE=...`
  end-to-end (llama generates the TS code + tests).
