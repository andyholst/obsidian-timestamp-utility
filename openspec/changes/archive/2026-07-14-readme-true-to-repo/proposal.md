# Proposal: ReadmeTrueToRepo

## Why

The `README.md` was written before (and partly alongside) the OpenSpec-driven agentic pipeline
took its current shape. Several statements are now **factually wrong** against the actual repo,
which misleads contributors. This change corrects those statements while **preserving the README's
existing format and structure** (headings, bullet style, code-fence examples). Evidence (from the
live `Makefile` and `AGENTS.md`):

- **False MCP claim** (lines ~264-265): "Integration tests and agentics require persistent MCP
  server on localhost:3003. Run `make start-mcp-persist &`" — `start-mcp-persist` does **not**
  exist in the Makefile, and `AGENTS.md` states the system is "docker compose (no Dagger, no MCP)".
  This must be removed.
- **Wrong `make run-agentics` usage** (lines ~210-232): README says `make run-agentics
  ISSUE_URL=...` (a GitHub issue) and tells the user to run `make build-image-agents` first and
  check `agentics.log`. The real target is `make run-agentics CHANGE=<openspec-change-name>` (a
  LOCAL OpenSpec change, no GitHub fetch). `build-image-agents` does not exist (compose builds the
  image), and there is no `agentics.log` file.
- **Wrong test filenames** (lines ~237-238): `test_ticket_interpreter.py` /
  `test_ticket_interpreter_integration.py` — the real suites live under
  `agents/agentics/tests/unit/` and `agents/agentics/tests/integration/` with different names.
- **Wrong model defaults** (Prerequisites): README lists `LLAMA_REASONING_MODEL=qwen3.5:9b` /
  `LLAMA_CODE_MODEL=qwen3.5:4b`. The Makefile defaults are `qwen3.6-35b-a3b`
  (both reasoning and code).

## What Changes

- Remove the MCP/localhost:3003 note from "Running Integration Tests".
- Rewrite "Steps to Run the Agent" to use `make run-agentics CHANGE=<name>` (local OpenSpec change),
  drop `build-image-agents` + `agentics.log`, keep the same heading/bullet/code-fence style.
- Fix the test filenames reference to point at the real `agents/agentics/tests/{unit,integration}`
  layout (without inventing specific file names that may drift — describe the directory).
- Correct the `OLLAMA_*` model defaults to the Makefile values.
- Keep every heading, the Documentation section, and the overall tone/format unchanged.

## Capabilities

- `readme-docs` (extends existing): the README is accurate to the current repo and uses the real
  Makefile commands/env.

## Impact

- Documentation only — no change to the loop-harness gates, the deterministic floor, or generated
  TS/test code (B4/B14: no git commit/push).
- MUST NOT regress: `make loop-unit` / `make loop-collect` still green (no Python source touched).
