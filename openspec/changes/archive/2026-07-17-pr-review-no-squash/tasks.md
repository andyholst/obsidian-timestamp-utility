# Tasks

> Executable plan for the `pr-review-no-squash` change (B28 — PR-review stability). Tick each
> box the moment the work is DONE + VERIFIED (B16). This change is built DIRECTLY on the
> `make-agent-create-worktree-and-pr-based-on-openspec` branch (not a separate worktree) per the
> user's instruction, and delivered to PR #55 as NORMAL (non-squashed) commits — no squash, no
> force-push — because PR #55 already has reviewer engagement (2 reviews).

## 1. OpenSpec scaffolding (change of record)
- [x] 1.1 Scaffold via the real CLI: `make openspec-new NAME=pr-review-no-squash CAPABILITY=pr-review-stability` (B15) — validated green
- [x] 1.2 Write `proposal.md` (Why / What / Capabilities / Impact)
- [x] 1.3 Write `specs/pr-review-stability/spec.md` in delta format (ADDED Requirements + Scenarios for no-squash-on-engaged-PR + gh-driven resolution)
- [x] 1.4 `openspec validate pr-review-no-squash` passes

## 2. Implement the no-squash guard (B28a)
- [x] 2.1 Add a PR-engagement pre-flight to the `squash-commits` Makefile target: via `gh pr view --json number,comments,reviews`, if the current branch is an open PR with `comments > 0` OR `reviews > 0` OR a non-dismissed review thread, FAIL CLOSED (message names the PR, states B28 forbids squash) and performs NO commit/reset/push. Skip the guard (fail-open) when `gh`/token is unavailable.
- [x] 2.2 Extend the guard to `loop-finish` and `openspec-redeliver` so they also refuse to squash/force-push an engaged PR (they both ultimately call `squash-commits`; verify the failure propagates and aborts cleanly with no history rewrite).

## 3. Implement gh-driven PR resolution (B28b)
- [x] 3.1 Add `scripts/pr_resolve.sh <branch>`: resolves the PR number for `<branch>` via `gh pr view --json ...`, prints the consolidated comment + review-thread list, and refuses (exit non-zero, no commit/push) when no open PR exists for the branch.
- [x] 3.2 Add a `pr-resolve` Makefile target: `pr-resolve BRANCH=<branch>` that invokes `scripts/pr_resolve.sh` and documents the agent loop (read each comment → fix → normal Conventional commit → normal push, never force/squash).
- [x] 3.3 Document the resolution procedure in AGENTS.md B28b: the agent follows each comment strictly, commits fixes as normal (non-squashed) Conventional commits, pushes normally, and never force-pushes or squashes an engaged PR.

## 4. B8 doc-sync (MUST stay green)
- [x] 4.1 Add B28 to AGENTS.md (durable behaviours) describing B28a + B28b, and bump the B-range literal B1–B27 → B1–B28.
- [x] 4.2 Bump the B-range literal B1–B27 → B1–B28 in the `openspec-loop-harness` skill, `docs/openspec-engineering-loop-harness.md`, the Makefile canonical comment, and `scripts/run-loop-harness.sh`.
- [x] 4.3 Run `make check-docs-sync` → PASS; `tests/test_check_docs_sync.py` green (the B-range fixture reflects B1–B28).

## 5. Verify (REAL, bounded — final task)
- [x] 5.1 `openspec validate pr-review-no-squash` passes
- [x] 5.2 `make check-docs-sync` passes
- [x] 5.3 Simulate the guard: `make squash-commits` on the current branch (PR #55, has 2 reviews) FAILS CLOSED with the B28 message and performs no history rewrite (HEAD unchanged before/after — verified).
- [x] 5.4 `bash scripts/pr_resolve.sh make-agent-create-worktree-and-pr-based-on-openspec` prints PR #55's comments/reviews (the real reviewer comment at L561) and exits 0 (no commit/push performed by the script itself).
- [x] 5.5 Resolve the surfaced review comment (B28b): clarify "loop gate-green" steps in `docs/openspec-engineering-loop-harness.md` (L561) as a NORMAL (non-squashed) commit.
- [x] 5.6 Commit the B28 work as NORMAL (non-squashed) Conventional commits on this branch and push normally (no force, no squash) to update PR #55.
