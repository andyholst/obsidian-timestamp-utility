# Timestamp Plugin for Obsidian

This plugin adds six commands for timestamps, date ranges, and task processing:

- **Insert Current Timestamp (YYYYMMDDHHMMSS)**
- **Rename Current File with Timestamp Prefix**
- **Rename Current File with Timestamp + First Heading Title**
- **Rename Current File with First Heading Title Only**
- **Insert Dates in Range (YYYY-MM-DD)**
- **Convert Reminders to Date-Time-Blocked Tasks**

## Plugin Development

See `AGENTS.md` for the full development guide. Key points:

- **Makefile only**: `make help` first. Never run npm/docker/ollama/Python directly.
- `make build-app` → builds plugin to `dist/`
- `make test-app` → runs Jest tests
- `make run-agentics ISSUE_URL=...` → runs AI agent to generate code from a GitHub issue

## Running the AI Agent

The agent uses LangGraph + Ollama to process GitHub issues and auto-generate TypeScript code and tests.

### Prerequisites

- `GITHUB_TOKEN` — GitHub PAT with repo access
- `OLLAMA_HOST` — Ollama URL (default: `http://localhost:11434`)
- `OLLAMA_MODEL` — **Must be `sorc/qwen3.5-claude-4.6-opus:9b`** (never bare `qwen3.5:9b`)

### Run

```bash
make run-agentics ISSUE_URL=https://github.com/andyholst/obsidian-timestamp-utility/issues/20
```

Set `PROJECT_ROOT` to your project path (auto-set by Makefile when run from project root).

### Testing

```bash
# Unit tests (fast, mocked)
make test-agents-unit-mock

# Full integration tests (needs real Ollama + GitHub)
make test-agents-integration

# All tests
make test-agents
```

### Architecture

See `agents/agentics/ARCHITECTURE.md` for the full agent architecture documentation.
