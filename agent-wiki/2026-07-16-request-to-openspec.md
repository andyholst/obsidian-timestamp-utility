# request-to-openspec — Work Log

**Date:** 2026-07-16
**OpenSpec Change:** `request-to-openspec`
**Branch:** `create-new-dashboard-telegram-behaviour`

## Summary
This change encodes a standing intake rule so that work arriving through any channel — the Hermes dashboard, Telegram, or the Hermes terminal CLI — is turned into an OpenSpec change (proposal + spec + tasks) and starts the loop, per an explicit per-channel trigger (dashboard always; Telegram/terminal only on the `openspec` keyword, else exempt). It closes the gap between "a request arrived" and "an OpenSpec change of record exists to describe it," and promotes the directive into a reusable Hermes skill loaded at request entry. A follow-up fix also extended the gate to the dashboard Kanban-delivery path after a live test showed the agent previously stopped at kanban tooling.

## Verification Against Spec
- Requirement "inbound requests are converted to an OpenSpec change before implementation": verified live across all four channels — dashboard Kanban task `t_7116ccad` scaffolded `readme-architecture-overview` (6.3), a Telegram `openspec` message scaffolded + archived `readme-align-with-commits` (6.2), the terminal-channel gate simulated on host (6.1), and the real `hermes chat` binary scaffolded `lint-fix-trailing-whitespace` while a non-`openspec` query stayed exempt (6.5); `openspec validate request-to-openspec` reports the change valid ✅
- Requirement "the intake rule is loaded at request entry": verified — the directive was promoted into the reusable `request-to-openspec` skill with per-channel worked examples (2.1/2.2) and B8-synced into AGENTS.md, openspec-loop-harness.md, and docs/openspec-engineering-loop-harness.md so it loads at request entry (3.2) ✅

## Key Decisions
- Removed the wrongly-placed `request_intake.py` / `request_intake_runner.py` / `test_request_intake.py` from `agents/agentics/src/` (Task 5.1): the intake gate is an agent-instruction concern (Hermes skill + AGENTS.md), not part of the Python codegen pipeline, which must hold zero knowledge of Hermes channels; no other `agents/` module referenced them.
- Extended the gate to the dashboard Kanban-delivery path (6.4): the Kanban wrapper is treated as a delivery envelope only, and the agent must still run `make openspec-new` / `openspec new change` to scaffold the change — correcting a live failure where the agent stopped at `kanban_show`/`kanban_complete`.
- B8-synced the intake gate across four sources (AGENTS.md General Rules, hermes/skills/openspec-loop-harness.md Known pitfalls, docs/openspec-engineering-loop-harness.md, and the `request-to-openspec` skill) so all agree on the per-channel trigger.
- Regenerated doc-sync fixtures via `make regen-doc-sync-fixtures` and re-ran `make check-docs-sync-and-test` → 33/33 green, keeping the live docs-sync gate passing (4.1).

## Current Status
Complete — `openspec validate` is green and all 9 tasks are ticked and verified live across the dashboard, Telegram, terminal-simulation, and real Hermes CLI channels.

## Recommended Next Steps
- Add a `design.md` artifact if the project convention requires it: `openspec status` shows `[ ] design` unchecked (the only incomplete artifact), though `openspec validate` passes and both spec requirements are verified.
- None otherwise — archive.
