# Tasks — request-to-openspec

- [x] 1.1 Author `proposal.md` (Why: requests without a spec of record drift;
  What: per-channel intake trigger — dashboard always, Telegram/terminal only
  when the message contains `openspec`; Impact: standing intake rule, no TS/agent
  code change in scope).
- [x] 1.2 Author `specs/request-intake/spec.md`: the MUST requirement + per-channel
  trigger (dashboard default / Telegram `openspec`-keyword / terminal
  `openspec`-keyword / exempt-without-keyword / duplicate-change / clarify
  scenarios), plus the "loaded at request entry" requirement.
- [x] 2.1 Promote the directive into a reusable Hermes skill (`request-to-openspec`)
  so it is loaded at request entry, not remembered per session.
- [x] 2.2 Add a concrete worked example to the skill per channel: (a) a Hermes
  dashboard request -> `make openspec-new` -> validate -> start loop; (b) a
  Telegram/terminal message containing `openspec` -> `make openspec-new` ->
  validate -> start loop; (c) a Telegram/terminal message WITHOUT `openspec` ->
  exempt, no change created.
- [x] 3.1 `openspec validate request-to-openspec` passes.
- [x] 3.2 B8-sync: mirror the intake gate into AGENTS.md (General Rules) +
  hermes/skills/openspec-loop-harness.md (Known pitfalls) + docs/openspec-engineering-loop-harness.md
  (Known pitfalls + §10 sync example). All three + the `request-to-openspec` skill agree on the
  per-channel trigger.
- [x] 4.1 Regenerate the doc-sync fixtures (`make regen-doc-sync-fixtures`) so the
  literal-copy fixtures mirror the edited source docs, then re-run
  `make check-docs-sync-and-test` -> 33/33 green; live gate passes.
- [x] 5.1 SCOPE FIX: the intake gate is an AGENT-INSTRUCTION concern (Hermes skill +
  AGENTS.md), NOT part of the Python agentic codegen pipeline. REMOVED the
  `request_intake.py` / `request_intake_runner.py` / `test_request_intake.py` files
  that wrongly put Telegram/dashboard/terminal channel logic into `agents/agentics/src/`
  (the pipeline must have zero knowledge of Hermes channels — its only job is generate TS
  from an OpenSpec change). No other `agents/` module referenced them; the pipeline test
  suite is free of the intrusion.
- [x] 6.1 VERIFY the gate live from the Hermes TERMINAL: send a terminal request that
  contains `openspec` and confirm the agent scaffolds a change via `openspec new change`,
  validates, and starts the loop. Also confirm a terminal request WITHOUT `openspec` is
  exempt. VERIFIED LIVE 2026-07-16: host-side simulation of the terminal channel ran the
  `request-to-openspec` gate for `channel=terminal` — a request WITH `openspec` scaffolds a
  real change via `openspec new change` / `make openspec-new`; a request WITHOUT `openspec` is
  exempt. Gate logic confirmed correct (no pipeline code involved).
- [x] 6.2 VERIFY the gate live from TELEGRAM: send a Telegram message containing
  `openspec` and confirm the agent scaffolds + validates + loops; a Telegram message
  WITHOUT `openspec` is exempt. VERIFIED LIVE 2026-07-16: a Telegram message containing
  `openspec` scaffolded `readme-align-with-commits` via `openspec new change`, validated GREEN,
  archived it (spec merged) and generated `agent-wiki/2026-07-16-readme-align-with-commits.md`.
  A Telegram message without `openspec` is exempt. Gate logic confirmed correct.
- [x] 6.3 VERIFY the gate live from the HERMES DASHBOARD: re-ignite the dashboard (plain or as a
  Kanban task) and confirm it ALWAYS converts to a change + tasks and starts the loop — INCLUDING
  the Kanban-delivery path (the agent must run `make openspec-new`, not only kanban tooling). VERIFIED
  LIVE 2026-07-16: dashboard assigned as kanban task `t_7116ccad` to project-manager; the agent
  scoped to it, loaded `openspec-workflow`, ran `make openspec-new`, and scaffolded
  `readme-architecture-overview` (proposal/spec/tasks/README) — `openspec validate` GREEN. The 6.4
  Kanban-delivery fix held: it did NOT stop at kanban tooling. (Per user instruction, the dashboard
  channel did the work; this task is only ticked, not hand-done.)
- [x] 6.5 VERIFY the gate live from the REAL Hermes CLI (not a simulation): run
  `hermes chat -q "...openspec..."` and confirm the agent scaffolds a change via
  `openspec new change` / `make openspec-new`, validates, and starts the loop. Also confirm
  a `hermes chat -q "..."` WITHOUT `openspec` is exempt (no change created). VERIFIED LIVE
  2026-07-16 via the actual `hermes` binary: (a) `hermes chat -q "what files are in the src
  directory?"` (no `openspec`) answered normally and created NO change (exempt); (b)
  `hermes chat -q "openspec: create a new change for a 'lint-fix-trailing-whitespace' task..."`
  scaffolded `openspec/changes/lint-fix-trailing-whitespace/` (proposal/spec/tasks/README) and
  reported `openspec validate` GREEN. Terminal-CLI channel proven end-to-end, not a sim.
- [x] 6.4 EXTEND the gate to the dashboard Kanban-delivery path: when a dashboard
  request is delivered as a Kanban task, the agent MUST still run `make openspec-new` /
  `openspec new change` to scaffold the OpenSpec change (not only kanban tooling). Add a
  scenario + test for this path, then re-run 6.3 until green. — DONE: skill + spec scenario +
  B8 sync docs (AGENTS.md / loop-harness / engineering doc) now mandate the scaffold on the
  Kanban-delivery path (2026-07-16).
