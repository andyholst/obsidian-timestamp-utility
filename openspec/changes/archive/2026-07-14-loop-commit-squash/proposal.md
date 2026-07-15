# Proposal: `make commit` — thorough Angular commit from changed files vs `main`, squashed into one

## Why
The branch (`setup-loop-harness-openspec`) carries the full feature's accumulated
work — ~114 commits / 243 changed files ahead of `origin/main`. A naive
`git commit` of the working tree (or of just the upstream-ahead commits)
produces a message about the *tooling* ("squash unpushed commits"),
not about **what the changed files actually do**. That fails the standing
rule: commits must be human-readable for others.

The `commit` Make target must instead:
1. Diff the **current branch against `main`** (the real base), not against the
   loose upstream.
2. Hand Hermes (project-manager profile) the **actual changed-file list + diff
   stats** and ask for a **THOROUGH** Conventional/Angular message: a
   `type(scope): subject` title plus a detailed body that explains the real
   behavioural changes across the substantive files (the OpenSpec loop-harness
   engineering, the deterministic code_integrator floor, the agentic pipeline,
   the Makefile / docker-compose / Containerfile changes, and the merged
   OpenSpec specs) — not meta commentary about the commit command itself.
3. Squash everything ahead of `main` into **one** commit on the current
   branch via `git reset --soft main && git commit`.
4. **Never push** (B14). If Hermes returns nothing, `git reset --quit`
   restores the pre-squash state so no partial/empty commit is left behind.

## What Changes
- `Makefile` `commit` target: base the diff on `origin/main` (fallback `main`),
  feed Hermes the changed-file list + `--stat` and instruct it to write a
  thorough, file-grounded Angular message; squash via `git reset --soft main`.
- No new runtime code; this is a developer-workflow (commit) change only.

## Capabilities
- `loop-commit-squash` (new) — see `specs/loop-commit-squash/spec.md`.

## Impact
- Every `make commit` yields one human-readable, behaviour-describing commit
  that a reviewer can act on, regardless of how many WIP commits piled up.
- History stays clean on the branch; push remains a deliberate, separate human step.
