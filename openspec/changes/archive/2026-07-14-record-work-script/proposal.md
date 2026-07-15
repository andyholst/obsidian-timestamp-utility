# Proposal: record-work-script

## Why

AGENTS.md **Phase 7** instructs the agent to "Call the `record-work` skill → write
`agent-wiki/YYYY-MM-DD-<name>.md`" after every OpenSpec change. But no `record-work`
skill was ever created — `agent-wiki/` entries have only ever been hand-written. This
leaves the documented Phase 7 step unfulfilled: the wiki is maintained manually and
drifts out of sync with the loop-harness gates (build/test/open-task status) that AGENTS.md
says every entry must capture.

We replace the missing skill with a **scriptable, deterministic tool** that produces the
same `agent-wiki` entry the skill was meant to, using the project-manager Hermes CLI
(`hermes -z`) to draft the prose — exactly like the existing `commit` Makefile target does
for commit messages. The tool is driven through the Makefile (`make record-work
CHANGE=<name>`) so it fits the existing OpenSpec workflow and B8 sync.

## What Changes

- Add `scripts/record-work.py`: a deterministic Python script that collects the inputs for a
  work-log entry (change `proposal.md` / `tasks.md` / `specs/**`, `openspec status`,
  `openspec validate`, git branch + recent commit, and a best-effort loop-gate summary) and
  calls `hermes -z` (profile `project-manager`) to draft the `agent-wiki` entry body, then
  writes `agent-wiki/YYYY-MM-DD-<change>.md` and appends a line to `agent-wiki/index.md`.
- Add a `record-work` Makefile target (`b9-perms` prerequisite so the container write works
  under rootless nerdctl) that invokes the script with `CHANGE` and an optional `DATE`.
- B8-sync AGENTS.md Phase 7 + the `openspec-loop-harness` skill to reference
  `make record-work` / `scripts/record-work.py` instead of the non-existent `record-work`
  skill.

## Capabilities

- `record-work` (new): scriptable OpenSpec-change → agent-wiki work-log entry.

## Impact

- No changes to the agentic TS-generation pipeline, the loop-harness gates, or the
  deterministic floor.
- `agent-wiki/` gains one entry per completed change, automatically, matching the existing
  hand-written format (`Date / OpenSpec Change / Branch / Summary / Verification Against
  Spec / Key Decisions / Problems & Solutions / Current Status / Recommended Next Steps`).
- No git commit/push (B4/B14): the target writes only `agent-wiki/` files; committing the
  wiki is a deliberate human step.
