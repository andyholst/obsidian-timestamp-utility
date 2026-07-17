# Tasks

> Executable plan for the `pr-agent-comment-resolve` change (B29 — two-way PR interaction). Tick each
> box the moment the work is DONE + VERIFIED (B16). Built DIRECTLY on the
> `make-agent-create-worktree-and-pr-based-on-openspec` branch (not a separate worktree) per the
> user's instruction; delivered to PR #55 as NORMAL (non-squashed) commits — no squash, no force-push
> (B28a: PR #55 already has reviewer engagement).

## 1. OpenSpec scaffolding (change of record)
- [x] 1.1 Scaffold via the real CLI: `make openspec-new NAME=pr-agent-comment-resolve CAPABILITY=pr-agent-comment-resolve` (B15) — validated green
- [x] 1.2 Write `proposal.md` (Why / What / Capabilities / Impact)
- [x] 1.3 Write `specs/pr-agent-comment-resolve/spec.md` in delta format (ADDED Requirements: comment the fix + commit on green gate)
- [x] 1.4 `openspec validate pr-agent-comment-resolve` passes

## 2. Implement B29a — comment the fix
- [x] 2.1 Add `scripts/pr_comment.sh <branch> <body>`: posts a PR comment via `gh pr comment`, refuses (exit non-zero) when no open PR / no token, prints the posted comment URL.
- [x] 2.2 Add a `pr-comment` Makefile target: `pr-comment BRANCH=<b> BODY=<text>` invoking `scripts/pr_comment.sh`.

## 3. Implement B29b — commit on green gate (no squash)
- [x] 3.1 Add a `pr-resolve-and-comment BRANCH=<b>` Makefile target: fetch threads (`pr_resolve.sh`), the agent applies fixes, runs `make loop-harness` (B20 pre-flight); when GREEN it commits normally, posts fix comments (`pr_comment.sh`), and pushes normally (no force/squash). When RED it stops and reports the failing stage.
- [x] 3.2 Document the procedure in AGENTS.md B29: B29a comment-the-fix; B29b commit-on-green-gate (normal push, no squash); B29c never self-resolve/approve.

## 4. B8 doc-sync (MUST stay green)
- [x] 4.1 Add B29 to AGENTS.md (durable behaviours) describing B29a/B29b/B29c, and bump the B-range literal B1–B28 → B1–B29.
- [x] 4.2 Bump the B-range literal B1–B28 → B1–B29 in the `openspec-loop-harness` skill, `docs/openspec-engineering-loop-harness.md`, the Makefile canonical comment, and `scripts/run-loop-harness.sh`.
- [x] 4.3 Run `make check-docs-sync` → PASS; `tests/test_check_docs_sync.py` green (B-range fixture reflects B1–B29).

## 5. Verify (REAL, bounded — final task)
- [x] 5.1 `openspec validate pr-agent-comment-resolve` passes
- [x] 5.2 `make check-docs-sync` passes
- [x] 5.3 `bash scripts/pr_comment.sh make-agent-create-worktree-and-pr-based-on-openspec "test comment"` posts a PR comment on #55 and prints its URL (verifies B29a end-to-end via gh).
- [x] 5.4 Run `make loop-harness` on this branch (B20 pre-flight); on GREEN, commit the B29 work as NORMAL (non-squashed) Conventional commits and push normally (no force, no squash) to update PR #55 — and post a PR comment describing the B29 addition (B29a demonstrated on the live PR). Committed as `b99d42a`; PR comment #4999193057.
- [x] 5.5 Verify the PR #55 diff shows the B29 change as incremental (non-squashed) commits. PR #55 shows `119f9f0` (B28) + `b99d42a` (B29) as separate normal commits.
