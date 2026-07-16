# Proposal: Request To OpenSpec

## Why
Work arrives through multiple entry channels — Telegram messages, the Hermes
dashboard, and the Hermes terminal CLI — and the agent historically starts
acting on these requests as ad-hoc one-offs. Without a spec of record, that
drift is invisible: changes are implemented without a proposal, acceptance
criteria, or a task list, so there is nothing to verify against, nothing to
archive, and no audit trail of *why* a behaviour exists. The OpenSpec loop in
this repo already mandates "the OpenSpec change is the source of truth" (B10)
and "every change gets its own worktree" (B24); the missing piece is the
**front door** — a standing rule that a request is turned into an OpenSpec change
(+ tasks) and the loop is started, according to a per-channel trigger. This
closes the gap between "a request arrived" and "an OpenSpec change exists to
describe it".

## What Changes
Encode a standing intake rule with an explicit per-channel trigger:

- **Hermes dashboard** — ALWAYS converts by default. Every dashboard work request
  becomes an OpenSpec change (via `make openspec-new` / `openspec new change`,
  per B15), the spec + tasks are created, `openspec validate` goes green, and the
  loop starts. No keyword required.
- **Telegram** — converts / creates tasks / starts the loop ONLY when the message
  contains the keyword `openspec` (case-insensitive). Messages without it are
  exempt (not turned into a change).
- **Hermes terminal CLI** — converts / creates tasks / starts the loop ONLY when
  the command/text contains the keyword `openspec` (case-insensitive). Requests
  without it are exempt.

Degenerate cases: re-use an existing in-flight change for the same intent (no
duplicate directory), and allow a `clarify` round to disambiguate *before*
scaffolding. The directive is promoted into a reusable Hermes skill /
system-level instruction so it is loaded at request entry (Tasks 2.x).

## Capabilities
- `request-intake` (new): per-channel inbound requests become OpenSpec changes
  (and start the loop) according to the trigger rule above.

## Impact
- Every piece of triggered work now has a proposal + spec + task list of record;
  the existing loop gates (validate, build-app, test-app, archive) operate on
  real changes, not ad-hoc edits.
## Known Limitations (verified 2026-07-16)
- **Dashboard → Kanban delivery gap.** When a Hermes dashboard work request is delivered
  to the agent as a **Kanban task** (the dashboard assigns it into a kanban workspace),
  the agent scopes to that task and runs kanban tooling instead of `make openspec-new` /
  `openspec new change`. The request is *accepted and converted* (not exempt), but the
  intake gate's "scaffold the change" step does NOT fire on the kanban-delivery path, so
  no OpenSpec change is created. Live test: project-manager received the dashboard task,
  ran `kanban_show`/`kanban_complete`, and ended the turn WITHOUT scaffolding a change.
  Task 6.3 therefore stays UNCHECKED until the gate is extended to cover dashboard
  requests delivered as kanban tasks (or the dashboard delivers them as plain requests).
  The Telegram and Hermes-terminal channels were verified working against the gate.
- No new generated TS / Python agent behaviour in this change — it is a
  behavioural/standing-rule change plus a skill promotion. The deterministic
  floor (B10/B11) and no-commit/no-push gate (B4/B14) are unaffected and MUST
  NOT regress.
- Reusing an existing change (when the trigger fires but a matching change is
  in-flight) prevents duplicate `openspec/changes/*` directories.
