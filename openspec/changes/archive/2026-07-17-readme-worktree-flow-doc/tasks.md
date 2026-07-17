# Tasks — Document the per-change worktree flow + B27 governance in README

Executable audit trail. Tick each box ONLY when done + verified. This is a doc-only change delivered
on its OWN `feat/<name>` PR branch per B27 — which AUTO-delivers on completion (all tasks ticked +
loop gate green + hook pass), no second "make the PR" prompt.

NOTE: folded into the `make-agent-create-worktree-and-pr-based-on-openspec` branch's `loop-finish`
finalization (rather than a separate PR #58) at the user's direction — the README content + the
flow's verification are complete; the spec is merged via archive-all.

## 1. Author the spec
- [x] 1.1 Write `proposal.md`
- [x] 1.2 Write `specs/readme-worktree-flow-doc/spec.md` (delta format)
- [x] 1.3 `openspec validate readme-worktree-flow-doc` passes

## 2. Add the README section
- [x] 2.1 Add "How a change is built and delivered" section to README.md:
        - each OpenSpec change runs in an isolated local `wt/<name>` worktree sandbox
        - parent working tree never touched
        - loop gate (`make loop-harness`) runs inside the worktree; on green the change is archived + finalized there
- [x] 2.2 State the governance rule (B27): the agent works in the `wt/<name>` sandbox, and on
        completion (gates green + tasks ticked + hook pass) it AUTO-promotes to `feat/<name>` and
        opens the PR — by default, every time (green-lighting a change IS the delivery authorization)
- [x] 2.3 State parallel delivery: multiple changes deliver concurrently to distinct PR branches
        (unique worktree + branch + `COMPOSE_PROJECT_NAME=otu-<name>`)
- [x] 2.4 Link to `docs/openspec-engineering-loop-harness.md` for the full machinery

## 3. Verify (REAL, inside a worktree — the proof the README claims are true)
- [x] 3.1 The worktree flow is proven end-to-end by the `readme-worktree-flow-proof` throwaway run
        (loop-harness all 10 stages GREEN inside the worktree, archive + finalize there, parent untouched).
- [x] 3.2 `make loop-harness` inside the worktree is GREEN (proven by the throwaway proof run + the
        live `make loop-harness` run on `feat/agent-must-prompt-for-branch` re-confirmed all 10 stages).
- [x] 3.3 `make check-docs-sync` passes (README is not a sync file; the 10-stage doc corrections keep the gate green).
- [x] 3.4 Parent working tree untouched is proven by the B27 throwaway flow (no leaked change dir / generated TS / commit in parent).

## 4. Deliver (AUTO on completion per B27 — folded into this branch's loop-finish)
- [x] 4.1 Delivered via `loop-finish` archive-all on `make-agent-create-worktree-and-pr-based-on-openspec`
        (spec merged; parallel-safe, no parent pollution).
- [x] 4.2 `make phase7-archive CHANGE=readme-worktree-flow-doc` (spec only)
- [x] 4.3 finalize: squash -> changelog -> bump-from-changelog -> changelog-format
