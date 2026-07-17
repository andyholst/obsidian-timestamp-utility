# Proposal: pr-review-no-squash (B28 — PR-review stability)

## Why
Today the harness squashes all commits ahead of `main` into a single commit on
delivery/finalization (`squash-commits`, `loop-finish`, `openspec-redeliver`). Once a
branch is live as a PR and a human has started reviewing it (comments or reviews),
squashing + force-pushing **rewrites history** and forces the reviewer to re-read every
file from scratch — destroying the incremental diff they were working through. That is a
poor review experience and a real correctness risk (a rebase/squash can silently drop a
fix). We need a durable rule: after a PR has reviewer engagement, the branch is frozen
against squash; all further corrections land as normal, reviewable commits.

Additionally, when a human says "go to the PR for `<branch>`" (or "address the PR
comments"), the agent currently has no defined procedure — it may silently re-run the
whole flow/squash. We need an explicit, gh-driven mode that fetches the PR's comments and
review threads and resolves each of them with code changes committed as normal commits,
then pushes normally (no force, no squash).

## What Changes
- **B28 (new durable behaviour)** in AGENTS.md + the loop-harness skill + the harness doc:
  - *B28a (no-squash-on-engaged-PR):* `squash-commits`, `loop-finish`, and `openspec-redeliver`
    MUST refuse (fail closed) when the current branch is the head of a PR that already has
    reviewer engagement — defined as `gh pr view` reporting `comments > 0` OR `reviews > 0`
    OR any non-dismissed review thread. After that point corrections are committed as normal
    Conventional commits on the PR branch and pushed normally.
  - *B28b (gh-driven PR resolution):* a "go to the PR for `<branch>`" instruction triggers a
    defined procedure — `make pr-resolve BRANCH=<branch>` / `scripts/pr_resolve.sh` — that uses
    the `gh` CLI to pull the PR's comments + review threads and prints them; the agent follows
    them strictly, makes the code fixes, commits each as a normal (non-squashed) Conventional
    commit, and pushes normally (never `--force`, never squash).
- **Makefile `squash-commits` guard:** a pre-flight PR-engagement check that fails closed
  (clear message) when the branch is an engaged PR head.
- **New `pr-resolve` Makefile target + `scripts/pr_resolve.sh`:** resolves a PR branch's
  comments via `gh` and documents the agent resolution loop.
- **B-range bump B1–B27 → B1–B28** across AGENTS.md, the loop-harness skill, the harness doc,
  and the Makefile canonical comment.

## Capabilities
- `pr-review-stability` (new): PR-review stability — no squash after reviewer engagement;
  gh-driven incremental comment resolution.

## Impact
- Must NOT regress: loop-harness gates, the deterministic `code_integrator` floor, B4/B14
  (no unrequested push — `pr-resolve` pushes only when the human asked to resolve/push), and
  B27 (worktree confinement for NEW changes — this rule only changes how an ALREADY-OPEN PR
  branch is updated).
- The guard is fail-open on `gh` unavailability: if `gh`/token is absent the squash proceeds
  (we never silently block a local squash purely for lack of network); it only blocks when
  `gh` confirms an engaged PR exists.
