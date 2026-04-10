# AGENTS.md

## Core
- **Makefile + Dagger only**: Run `make help` first. `make setup-dev` for Dagger/engine. **Never** run npm/docker/ollama/Python directly. Trust Makefile/Dagger pipelines over README.md.
- Env: Set `GITHUB_TOKEN` (agents), `OLLAMA_MODEL=qwen3.5:9b` (default), `OLLAMA_CODE_MODEL=qwen3.5:9b`. Use `make check-deps check-github check-mcp`.
- Structure: `src/` (Obsidian TS plugin), `agents/agentics/` (LangGraph agents + tests), `dagger-pipeline/` (all build/test logic). Plugin edits independent of agents.
- Cleanup: `make clean`, `make clean-dagger-engine` or `make nuke-dagger` for Dagger issues. `make fix-perms` auto-runs after most targets.

## Plugin (src/)
- Entry: `src/main.ts` (6 commands: timestamp insert/rename variants, date-range modal, reminder-to-task processor).
- Build/test: `make test-app` (Rollup CJS to dist/main.js + Jest in src/__tests__/). No separate lint; strict TS.
- Install: Copy `dist/main.js` + `manifest.json` to `.obsidian/plugins/timestamp-utility/` (exact match to manifest.id; avoid desktop-only APIs).
- CI: Only `make test-app` on non-main. Bump version in both package.json + manifest.json.
- **Never edit dist/**. Use `make build-app` before manual testing.

## Agents (agents/agentics/)
- Multi-agent LangGraph system (ticket → plan → codegen → test → review → integrate) with MCP on :3003.
- Quick verify: `make test-agents-unit-mock` (mocked, no Ollama).
- Full: `make start-mcp-persist &` then `make test-agents` or `make run-agentics ISSUE_URL=...` (needs GITHUB_TOKEN, live Ollama, TEST_ISSUE_URL).
- Tests target real issues (#20, #22, #23). Use `make lint-python` (ruff/mypy). Verbose/watch targets exist.

## Release
- `make release` after version bump (builds changelog + ZIP in release/).
- No pre-commit hooks. Avoid committing secrets.

## Gotchas
- MCP **must** run in background for any agentics, integration, or run-agentics.
- Dagger engine state is fragile; use dedicated start/stop/clean targets.
- README has outdated install paths/env vars — follow Makefile.
- For Obsidian plugin work only, ignore agents/ entirely.
