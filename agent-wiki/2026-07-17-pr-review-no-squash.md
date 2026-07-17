# pr-review-no-squash — Work Log

**Date:** 2026-07-17
**OpenSpec Change:** `pr-review-no-squash`
**Branch:** `make-agent-create-worktree-and-pr-based-on-openspec`

## Summary
This change introduces durable behaviour B28 — PR-review stability — which freezes a branch against squash/force-rewrite once it is the head of a pull request with reviewer engagement (comments > 0, reviews > 0, or a non-dismissed review thread). It also adds a gh-driven PR resolution mode so that when the human says "go to the PR for `<branch>`" the agent fetches the PR's comments and review threads and resolves each as a normal (non-squashed) Conventional commit, pushing normally. The work was built directly on the `make-agent-create-worktree-and-pr-based-on-openspec` branch (not a separate worktree, per the user's instruction) and delivered to PR #55 as regular commits because PR #55 already had 2 reviews.

## Verification Against Spec
- Requirement "No squash after a PR has reviewer engagement": verified by the new PR-engagement pre-flight in the `squash-commits`/`loop-finish`/`openspec-redeliver` Makefile targets plus task 5.3 — `make squash-commits` on PR #55 (2 reviews) failed closed with the B28 message and performed no commit/reset/push, HEAD unchanged before and after ✅
- Requirement "gh-driven PR comment resolution mode": verified by `scripts/pr_resolve.sh make-agent-create-worktree-and-pr-based-on-openspec` printing PR #55's comments/reviews (the real reviewer comment at `docs/openspec-engineering-loop-harness.md:561`) and exiting 0 (task 5.4), and by task 5.5 resolving that surfaced comment as a normal non-squashed commit ✅

## Key Decisions
- Built directly on the existing branch rather than a dedicated `wt/<name>` worktree, per explicit user instruction — B27 worktree confinement still applies to NEW changes, not to updating this already-open PR.
- Delivered to PR #55 as NORMAL (non-squashed) commits with a normal push, deliberately exercising B28a's "corrections after engagement land as normal commits" so the rule is proven by the change's own delivery, not just documented.
- Guard is fail-open when `gh`/token is unavailable (never silently blocks a local squash purely for lack of network) but fail-closed the moment `gh` confirms an engaged PR exists.
- Bumped the B-range literal B1–B27 → B1–B28 across AGENTS.md, `hermes/skills/openspec-loop-harness.md`, `docs/openspec-engineering-loop-harness.md`, the Makefile canonical comment, and `scripts/run-loop-harness.sh`, keeping `make check-docs-sync` green (task 5.2, `tests/test_check_docs_sync.py` reflects B1–B28).
- `pr-resolve` script refuses (exit non-zero, no commit/push) when no open PR exists for the branch, so it cannot accidentally create history on a non-PR branch.

## Current Status
Complete — all tasks ticked, `openspec validate` green, `make check-docs-sync` green, and PR #55 updated with normal non-squashed commits (the `design` artifact is intentionally left unticked as this doc/Makefile change required no design doc).

## Recommended Next Steps
None — archive.
