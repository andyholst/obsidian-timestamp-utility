# Tasks

> Executable plan for the `pr-fix-no-revert` change (B30 — never revert; squash pre-PR only). Tick
> each box the moment the work is DONE + VERIFIED (B16). Built DIRECTLY on the
> `make-agent-create-worktree-and-pr-based-on-openspec` branch (not a separate worktree) per the
> user's instruction; delivered to PR #55 as NORMAL (non-squashed) commits — no revert, no squash,
> no force-push (B28a/B30: PR #55 already has reviewer engagement).

## 1. OpenSpec scaffolding (change of record)
- [x] 1.1 Scaffold via the real CLI: `make openspec-new NAME=pr-fix-no-revert CAPABILITY=pr-fix-no-revert` (B15) — validated green
- [x] 1.2 Write `proposal.md` (Why / What / Capabilities / Impact)
- [x] 1.3 Write `specs/pr-fix-no-revert/spec.md` in delta format (ADDED Requirements: no revert ever; squash pre-PR only)
- [x] 1.4 `openspec validate pr-fix-no-revert` passes

## 2. Implement B30 (rule + guard)
- [x] 2.1 Extend the `squash-commits` Makefile pre-flight (B28a) so it ALSO refuses when the branch is a
  pushed/open-PR branch (any `gh pr view` open PR for the branch, not only reviewer engagement) — squash
  is pre-PR only. Fail-open on `gh` absence.
- [x] 2.2 Document B30a (no revert ever), B30b (squash pre-PR only), B30c (red gate → forward fix) in
  AGENTS.md, the loop-harness skill, and the harness doc. Reference the standing no-squash/no-force rule.

## 3. B8 doc-sync (MUST stay green)
- [x] 3.1 Bump the B-range literal B1–B29 → B1–B30 in AGENTS.md, `openspec-loop-harness` skill,
  `docs/openspec-engineering-loop-harness.md`, the Makefile canonical comment, and `run-loop-harness.sh`.
- [x] 3.2 Run `make check-docs-sync` → PASS; `tests/test_check_docs_sync.py` green (B-range fixture B1–B30).

## 4. Verify (REAL, bounded — final task)
- [x] 4.1 `openspec validate pr-fix-no-revert` passes
- [x] 4.2 `make check-docs-sync` passes
- [x] 4.3 Confirm `make squash-commits` on the current branch (PR #55, pushed + engaged) STILL fails
  closed (B28a/B30b) with no history rewrite (HEAD unchanged). Verified: exit 2, HEAD `5e267eb`.
- [x] 4.4 Run `make loop-harness` on this branch (B20 pre-flight); on GREEN, commit the B30 work as a
  NORMAL (non-squashed) forward commit and push normally (no revert, no squash, no force) to update PR #55. Committed `5e267eb`.
- [x] 4.5 Post a PR comment (B29a) on #55 describing the B30 addition and the never-revert rule. Posted #4999193057.
