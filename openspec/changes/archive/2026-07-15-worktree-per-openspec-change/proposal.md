# Proposal

## Why
On 2026-07-15 the agent destroyed hours of release-pipeline fix-work by running
`git reset --hard origin/main` during test cleanup — the uncommitted `changelog`/`bump` scripts
and Makefile edits were wiped permanently. The fixes had to be re-derived from scratch. The root
cause: lossy git operations (`reset --hard`, `checkout --`, `branch -D`) were run directly on the
active/parent branch where they can destroy authored, un-synced history.

## What Changes
Encode a standing engineering rule: **every OpenSpec change is implemented in its own isolated git
worktree**; all lossy/exploratory operations happen inside that worktree (where `reset`/`checkout`
cannot touch the parent), and the result is **synced back to the parent branch only when green**
(tasks ticked + `openspec validate` clean + loop gate green). The parent branch becomes read-mostly
for the agent — it may `commit`/`merge`/`cherry-pick`, but never `reset`/`checkout` past authored
work, and never `branch -D` a branch holding fix-work.

## Capabilities
- `openspec-workflow` (the per-change worktree rule + sync-back gate).

## Impact
- The parent branch is never corrupted by a failed/abandoned change: a broken change is abandoned by
  deleting its worktree + `wt/<name>` branch, leaving the parent untouched.
- Fix-work can never be silently reset away again (closes the 2026-07-15 incident).
- Each change's work is isolated and mergeable independently.
