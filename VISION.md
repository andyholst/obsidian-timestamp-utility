# VISION.md — Obsidian Timestamp Utility

## What This Is
An Obsidian plugin that inserts, renames, and manages timestamps in notes. Includes date-range modals, reminder-to-task processing, and (in agents/) a multi-agent LangGraph system for autonomous issue handling.

## Core Capabilities
1. **Timestamp Insert** — Insert configured timestamp format at cursor
2. **Timestamp Rename** — Rename existing timestamps in the note
3. **Date-Range Modal** — UI for selecting date ranges and generating timestamped content
4. **Reminder-to-Task** — Process reminder patterns into task items with dates
5. **Agentics System** — Multi-agent pipeline (ticket → plan → codegen → test → review → integrate)

## Plugin Architecture
- `src/main.ts` — Entry point, 6 commands, plugin lifecycle
- `src/commands/` — Command implementations
- `src/ui/` — Modals, settings, UI components
- `src/utils/` — Date formatting, parsing, helpers
- `__tests__/` — Jest test suite

## Agent Architecture
- `agents/agentics/` — LangGraph multi-agent graph
- MCP server on :3003 for tool access
- Dagger pipeline for build/test orchestration

## Anti-Drift Checks (run before every commit)
- [ ] All 6 commands registered and functional
- [ ] `make test-app` passes (strict TS + Jest)
- [ ] `dist/main.js` built before manual testing
- [ ] `manifest.json` version matches `package.json`
- [ ] No desktop-only APIs used (Obsidian mobile compatibility)
- [ ] Plugin installs cleanly to `.obsidian/plugins/timestamp-utility/`
- [ ] Version bump in both files before release

## Quality Standards
- TypeScript strict mode — no `any` without justification
- Tests cover new commands and utilities
- Commit messages: `feat/fix/refactor/refactor: what (why)`
- Never edit `dist/` directly
- No secrets in repo (tokens go in `.env` or GitHub secrets)

## Release Process
1. Bump version in `package.json` + `manifest.json`
2. Run `make test-app`
3. Run `make build-app`
4. Run `make release` (builds changelog + ZIP)
5. Tag release on GitHub
