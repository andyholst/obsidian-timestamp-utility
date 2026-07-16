# Proposal: Readme Align With Commits

## Why
The README still advertises "six convenient commands" and documents only the six original
commands in its Usage section. Since the README's Documentation section was last meaningfully
updated (commits d4790d5 / dcb310d), three new plugin commands have been committed to
`src/main.ts` but never documented:

- **Insert UUID v7 (timestamp-based)** — committed via `2026-07-15-uuid-modal-agentic-generation`
- **Encode Base64 Message** — committed via `2026-07-15-base64-tool`
- **Decode Base64 Message** — committed via `2026-07-15-base64-tool`

The plugin now registers **nine** commands. The README is out of sync with the newest committed
functionality, which misleads users and breaks the repo's own "documentation-driven" promise. The
README's Documentation section must also accurately point readers at the OpenSpec loop/harness
technical reference and the `AGENTS.md` agent-execution manual.

## What Changes
- Update the README intro from "six convenient commands" to "nine convenient commands" and add the
  three missing commands to the feature list.
- Add a Usage subsection for each of the three new commands, accurate to their current behaviour in
  `src/main.ts` (UUID v7 inserts at the cursor; Base64 encode/decode open a modal with a textarea +
  button and show the result in the modal).
- Confirm/refresh the Documentation section so it references `docs/openspec-engineering-loop-harness.md`
  (the authoritative loop/harness reference) and `AGENTS.md`, and note the `docs/openspec-loop-harness-guide.md`
  redirect.
- Docs only — **no** TypeScript / Python code changes.

## Capabilities
- `readme-alignment` (new): the README accurately reflects every registered plugin command and
  references the OpenSpec loop/harness docs + `AGENTS.md`.

## Impact
- Docs-only change; no generated TS, no agent behaviour change. The deterministic floor (B10/B11) and
  the no-commit/no-push gate (B4/B14) are unaffected and MUST NOT regress.
- The README is **not** part of the B8 four-file doc-sync set, so `make check-docs-sync` is not the
  gate here. The gate is README↔`src/main.ts` command parity (all 9 `addCommand` ids present) plus
  `openspec validate` green.
