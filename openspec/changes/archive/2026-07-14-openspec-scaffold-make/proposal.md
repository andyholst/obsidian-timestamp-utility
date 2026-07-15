# Proposal: openspec-scaffold-make

## Why

Every OpenSpec change in this repo is created by the `openspec new change <name>` CLI, then
hand-seeded with `proposal.md`, `tasks.md`, and `specs/<capability>/spec.md` in the
delta format the CLI validates. That seeding is currently done ad-hoc (copy a previous
change, edit by hand), so the *shape* of the change directory drifts between authors and
between sessions. There is no documented, reproducible harness that says "this is how we
create an OpenSpec change here."

We add a **Makefile target (`make openspec-new`)** that wraps the real `openspec` CLI
(never hand-writes the directory — per durable behaviour B15 the change dir is produced by
`openspec new change`, not by `Path.write_text`) and then seeds the conventional files from a
single template with the caller's `NAME` / `DESC` / `GOAL` / `CAPABILITY` arguments, finally
running `openspec validate` so the change is green before any implementation work begins.

## What Changes

- Add `scripts/scaffold-openspec-change.sh`: a thin, deterministic wrapper that
  1. invokes `openspec new change <NAME> --description <DESC> --goal <GOAL>` (the canonical CLI
     step — B15),
  2. writes `proposal.md`, `tasks.md`, and `specs/<CAPABILITY>/spec.md` from a heredoc template
     populated with the caller's args,
  3. runs `openspec validate <NAME>` and reports the result.
- Add a `openspec-new` Makefile target that passes `NAME` (required), `DESC`, `GOAL`,
  `CAPABILITY` through to the script, with `b9-perms` as a prerequisite (rootless nerdctl write
  floor) and a refusal when `NAME` is empty.
- B8-sync AGENTS.md Phase 2 + the `openspec-loop-harness` skill to reference `make openspec-new`
  as the canonical way to create a change.

## Capabilities

- `openspec-scaffold` (new): a Makefile/CLI harness that creates spec-compliant OpenSpec changes.

## Impact

- No change to the agentic TS-generation pipeline, the loop-harness gates, or the deterministic
  floor.
- Change directories are now created consistently (real CLI + validated template), so the four
  harness artifacts (Makefile / AGENTS.md / skill / script) agree on HOW a change is born.
- No git commit/push (B4/B14): the target writes only `openspec/changes/<NAME>/` files; committing
  is a deliberate human step.
