# request-intake Specification

## Purpose
TBD - created by archiving change request-to-openspec. Update Purpose after archive.
## Requirements
### Requirement: inbound requests are converted to an OpenSpec change before implementation
The agent MUST, upon receiving a new work request, create an OpenSpec change
that captures the request as a proposal (via `make openspec-new NAME=<derived>`,
which invokes the real `openspec new change` per B15, scaffolding `proposal.md`
/ `tasks.md` / `specs/<capability>/spec.md`), confirm `openspec validate <name>`
is green, then start the loop against that change — UNLESS the source channel's
trigger rule below says the request is exempt. The agent MUST NOT act on a
request as ad-hoc work without a change of record when the trigger applies.

**Trigger rule by entry channel:**
- **Hermes dashboard:** ALWAYS converts by default. Every dashboard work request
  becomes a change + tasks, and the loop starts — no keyword required.
- **Telegram:** converts / creates tasks / starts the loop ONLY IF the message
  contains the keyword `openspec` (case-insensitive). A Telegram message WITHOUT
  `openspec` is exempt and is NOT turned into a change.
- **Hermes terminal CLI:** converts / creates tasks / starts the loop ONLY IF the
  command/text contains the keyword `openspec` (case-insensitive). A terminal
  request WITHOUT `openspec` is exempt and is NOT turned into a change.

#### Scenario: request arrives via the Hermes dashboard
- **WHEN** a work request arrives through the Hermes dashboard
- **THEN** the agent scaffolds an OpenSpec change via `make openspec-new` /
  `openspec new change`, fills in the proposal + spec, validates it, creates the
  tasks, and starts the loop — by default, with no keyword needed.
#### Scenario: request delivered as a Kanban task still converts
- **WHEN** a work request is delivered to the agent AS a **Kanban task** (the channel assigns
  it into a kanban workspace, e.g. `/home/asimov/.hermes/kanban/workspaces/<task>` and the
  agent is scoped to that task)
- **THEN** the Kanban wrapper is treated as the *delivery envelope* only; the agent STILL applies
  the per-channel trigger and runs `make openspec-new` / `openspec new change` to scaffold the
  OpenSpec change of record (fill proposal/spec, validate, start loop). The agent does NOT limit
  itself to kanban tooling (`kanban_show` / `kanban_complete` / `kanban_comment`) — it scaffolds
  the change, then may update/close the kanban task afterwards. (Corrected 2026-07-16 after a live
  test showed the agent stopped at kanban tooling and never scaffolded; the gate now mandates the
  scaffold on the kanban-delivery path.)

#### Scenario: Telegram message contains "openspec"
- **WHEN** a work request arrives through Telegram AND the message contains the
  keyword `openspec` (e.g. "make a new openspec for the dashboard")
- **THEN** the agent scaffolds an OpenSpec change, validates it, creates the
  tasks, and starts the loop against it.

#### Scenario: Telegram message without "openspec" is exempt
- **WHEN** a message arrives through Telegram but does NOT contain the keyword
  `openspec`
- **THEN** the agent does NOT create a change / tasks / loop for it. The request
  is exempt from conversion.

#### Scenario: Hermes terminal command contains "openspec"
- **WHEN** a work request arrives via the Hermes terminal CLI AND the text
  contains the keyword `openspec` (e.g. "openspec new change for the exporter")
- **THEN** the agent scaffolds an OpenSpec change, validates it, creates the
  tasks, and starts the loop against it.

#### Scenario: Hermes terminal request without "openspec" is exempt
- **WHEN** a request arrives via the Hermes terminal CLI but does NOT contain the
  keyword `openspec`
- **THEN** the agent does NOT create a change / tasks / loop for it. The request
  is exempt from conversion.

#### Scenario: a change already exists for the same intent
- **WHEN** the incoming request (that triggers conversion) maps to an in-flight
  OpenSpec change (same or substantially the same intent)
- **THEN** the agent loads that change (`openspec status --change <name>` /
  `load_change`) and continues against it, rather than scaffolding a duplicate
  change directory.

#### Scenario: ambiguous request is clarified before scaffolding
- **WHEN** the incoming request is ambiguous and needs disambiguation
- **THEN** the agent MAY use `clarify` to resolve the ambiguity, and the eventual
  work still becomes an OpenSpec change of record before implementation begins.

### Requirement: the intake rule is loaded at request entry
The "requests become OpenSpec proposals (per channel trigger)" directive MUST be
available to the agent as a reusable instruction — promoted into the Hermes skill
(or a system-level instruction) so it is loaded whenever a new request enters,
not remembered manually per session.

#### Scenario: instruction is reusable
- **WHEN** a new session starts and the first message is a work request
- **THEN** the intake rule is already in context (via skill/system instruction),
  so the agent applies the correct per-channel trigger before acting without
  being reminded.

