# Proposal: Document the per-change worktree flow + branch-governance rule in README

## Why
The repo now has a per-change OpenSpec worktree flow (`make openspec-flow` / `scripts/openspec-change-flow.sh`)
and a clear branch-governance rule (default = local `wt/<name>` sandbox; a named remote `feat/<name>`
PR branch is created ONLY on explicit human say-so, parallel-safe). The README — the human-facing
entry point — does NOT mention either, so users have no doc-level map of how a change is isolated,
verified, and delivered. This change adds a concise, accurate README section so the workflow is
discoverable from the product doc itself.

## What Changes
- Add a "How a change is built and delivered" section to README.md covering:
  - Each OpenSpec change runs in an isolated **local worktree** sandbox (`worktrees/<name>`, branch `wt/<name>`)
    so the parent working tree is never touched.
  - The loop gate (`make loop-harness`) runs INSIDE the worktree; on green the change is archived and finalized there.
  - Delivery is a named remote PR branch (`feat/<name>`), created ONLY when a human explicitly says
    "make the PR" — never automatically for every change. Multiple changes deliver in parallel to
    distinct PR branches (governance rule B27).
- Cross-link to `docs/openspec-engineering-loop-harness.md` for the full machinery.

## Capabilities
- `readme-worktree-flow-doc` — README documents the worktree flow + branch governance.

## Impact
- README.md only (doc change). No TS, no pipeline. Verified via the doc-sync gate + a real end-to-end
  pass of the flow (which proves the README's claims are true). Delivered on its own `feat/<name>`
  branch as a separate PR, per B27.
