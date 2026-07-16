# readme-align-with-commits — Work Log

**Date:** 2026-07-16
**OpenSpec Change:** `readme-align-with-commits`
**Branch:** `create-new-dashboard-telegram-behaviour`

## Summary
The README still advertised "six convenient commands" while the plugin now registers nine — three new commands (insert-uuid-v7, encode-base64-message, decode-base64-message) had been committed to src/main.ts but never documented. This change restores README↔src/main.ts command parity (intro now says "nine", all three new commands added to the feature list and given Usage subsections) and refreshes the Documentation section links to the OpenSpec loop/harness reference and AGENTS.md. It is a docs-only change, so no TypeScript or Python was touched.

## Verification Against Spec
- Requirement "README lists every currently registered plugin command": task 4.1 parity assert passed — all 9 addCommand ids (insert-timestamp, rename-with-timestamp, rename-with-timestamp-title, rename-filename-with-title, insert-date-range, insert-uuid-v7, encode-base64-message, decode-base64-message, process-tasks) present in README, intro rewritten to "nine"; openspec validate readme-align-with-commits green ✅
- Requirement "README Documentation section points at the loop/harness and AGENTS.md": task 3.1 verified working links to docs/openspec-engineering-loop-harness.md + AGENTS.md and noted the docs/openspec-loop-harness-guide.md redirect ✅
- Requirement "README describes only committed functionality": task 4.1 confirms every documented command maps to a real addCommand in src/main.ts — no phantom commands, newest committed behaviour (UUID v7 at-cursor insert; Base64 encode/decode modals) documented accurately ✅
- Note: the change-named spec file openspec/changes/readme-align-with-commits/specs/readme-align-with-commits/spec.md was left as a "TODO — name the requirement" placeholder; the substantive Requirements live in specs/readme-alignment/spec.md (the ADDED capability). validate still passed, but the stub is dead weight ⚠️

## Key Decisions
- Kept this strictly docs-only: no edits to src/main.ts or any agentic Python, so the deterministic floor (B10/B11) and the no-commit/no-push gate (B4/B14) are untouched and cannot regress.
- Recognised that README is not part of the B8 four-file doc-sync set, so `make check-docs-sync` is NOT the gate here; the real gate is README↔src/main.ts command parity plus a green `openspec validate`.
- Documented each new command to match its actual behaviour in src/main.ts: insert-uuid-v7 inserts a timestamp-based UUID at the cursor with no modal; encode/decode-base64-message open a modal with a textarea + button and show the result in the modal.
- Left the original-filename spec file as a TODO stub (substantive content authored under the readme-alignment capability spec) — flagged above for cleanup before archive.

## Current Status
Complete — all tasks ticked and `openspec validate readme-align-with-commits` reports the specification is valid.

## Recommended Next Steps
- Before archiving, remove or fold the empty `specs/readme-align-with-commits/spec.md` TODO stub into `specs/readme-alignment/spec.md` so the change dir does not carry a placeholder spec.
- Otherwise: None — archive.
