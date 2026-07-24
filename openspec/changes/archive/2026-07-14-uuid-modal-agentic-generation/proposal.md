## Why

Obsidian users need a fast way to insert unique, time-ordered identifiers for cross-note linking and referencing. Issue #20 ("Implement Current TimeStamp as UUID") requests a command that generates a **UUID v7** (48-bit millisecond timestamp + random bits) and inserts it at the cursor. We want this implemented by driving our existing Python agentic pipeline (`agents/agentics`) via the Makefile, exactly as the OpenSpec loop-harness prescribes: spec → tasks → implement-in-worktree → verify → document.

## What Changes

- Add a new "Insert UUID v7" command to the plugin, registered in `src/main.ts`.
- The UUID is generated from the current timestamp following the **UUID v7** standard (128-bit, version bits `0111`, variant bits `10`, securely-random remaining fields), formatted `xxxxxxxx-xxxx-7xxx-xxxx-xxxxxxxxxxxx`.
- The generated UUID is inserted at the active editor's cursor position.
- Generated/updated TypeScript lives in `src/main.ts` and the corresponding tests in `src/__tests__/main.test.ts` (these are the exact files the agentic `CodeIntegratorAgent` writes to via `PROJECT_ROOT`).
- The feature is produced by running the agentic pipeline through `make run-agentics` (default ticket = issue #20), executed inside a git worktree so the main tree stays clean until verification passes.

## Capabilities

### New Capabilities
- `uuid-v7-modal`: Generates a timestamp-based UUID v7 and inserts it at the cursor via a new Obsidian command. Covers generation logic, command registration, and test coverage.

### Modified Capabilities
<!-- No existing spec-level behavior changes. The plugin already has timestamp commands; this adds a new sibling command. -->

## Impact

- Affected code: `src/main.ts` (new command + generation function), `src/__tests__/main.test.ts` (new tests), possibly `package.json`/manifest if a runtime dependency is required.
- Affected systems: the agentic pipeline (`make run-agentics`) and its LLM (Ollama `qwen3.6-35b-a3b`), which reads the GitHub issue and writes the TS files.
- Dependencies: none required if a UUID v7 is implemented with the Web Crypto / Node `crypto.randomUUID`-style randomness; otherwise a small npm helper. Decision deferred to `design.md`/agentic output.
- Note: execution currently depends on `make run-agentics`, which routes through Dagger-gated Makefile targets. This proposal's execution is validated via the agentic pipeline; the Dagger dependency is removed in the companion change `docker-make-no-dagger`.
