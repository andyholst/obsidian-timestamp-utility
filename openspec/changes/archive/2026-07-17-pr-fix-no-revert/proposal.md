# Proposal: pr-fix-no-revert (B30 — never revert; squash only pre-PR)

## Why
Two earlier corrections converge into one durable rule about git history on this project:
1. **Reverting commits is NEVER allowed** — not on `main`, not on a feature branch, and especially
   not on a PR branch that a human is reviewing. A `git revert` rewrites visible history and
   contradicts the "never modify committed history" guarantee the reviewer relies on.
2. **Squash is ONLY allowed while the work is still a local pre-PR change** — i.e. the commits have
   NOT yet been pushed / the branch is not yet an open PR. Once the branch is pushed and becomes an
   open PR (B28a: once it has reviewer engagement), squash is forbidden too, because squashing a
   public PR branch rewrites history the reviewer is working against.

Today `squash-commits` / `loop-finish` have no explicit "pre-PR only" guard beyond B28a's
engagement check, and there is no rule at all forbidding `git revert`. We make both explicit and
durable as **B30**.

## What Changes
- **B30 (new durable behaviour)** in AGENTS.md + skill + harness doc:
  - *B30a (no revert, ever):* the agent MUST NOT run `git revert` on any branch. Corrections are made
    by adding a NEW forward NORMAL commit, never by reverting an existing one.
  - *B30b (squash pre-PR only):* `squash-commits` / `loop-finish` / `openspec-redeliver` may squash
    ONLY while the branch is a LOCAL change that is not yet an open PR. They already refuse to squash
    an engaged PR (B28a); this makes the "pre-PR only" intent explicit and also forbids squash after a
    branch has been pushed even without comments (a pushed branch is public — squash would rewrite it).
  - *B30c (red gate → forward fix):* if the loop gate is RED after a push, the agent adds a NORMAL
    forward fixup commit (and, when applicable, a PR comment per B29a) — it NEVER reverts, resets,
    rebases, or squashes to "undo" the pushed work.
- **Makefile guard:** extend the `squash-commits` pre-flight so it also refuses when the branch has
  ANY pushed/public state (not just reviewer engagement) — i.e. if `gh pr view` finds an open PR for
  the branch (regardless of comments), or the branch tracks a remote that is ahead, squash is refused.
- **B-range bump B1–B29 → B1–B30** across AGENTS.md, skill, harness doc, Makefile, `run-loop-harness.sh`.

## Capabilities
- `pr-fix-no-revert` (new): reverting commits is never allowed; squash only before a branch becomes
  a PR; PR fixes are always forward normal commits.

## Impact
- Must NOT regress: B28a (no squash on engaged PR), loop-harness gates, B4/B14 (no unrequested
  push-to-main), and B27 (worktree confinement for NEW changes). B30 strengthens B28a, does not
  replace it.
- This is a documentation/guard hardening; it adds a pre-PR squash guard and a hard no-revert rule.
  No generated TS/test logic changes, so the loop gate is unaffected by B30 itself.
