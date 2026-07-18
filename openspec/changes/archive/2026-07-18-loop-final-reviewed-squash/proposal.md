# Proposal: loop-final — review-approved squash + changelog + force-push

## Why

Today B28a/B30b forbid the agent from ever squashing or force-pushing an **open PR**:
corrections after push must land as normal forward commits. That rule protects a reviewer's
incremental diff *while review is in progress*, but it has no "we're done" exit: once a human
reviewer has looked at the PR and explicitly approves it (e.g. replies **"PR looks great"**),
the owner wants the branch collapsed to ONE clean typed commit, the CHANGELOG regenerated from
that squash commit, and the result force-pushed to the feature branch — because the reviewer has
already seen the content and now wants tidy history for merge.

This change adds a **narrow, human-approval-gated exception** (`make loop-final`) that permits
squash + changelog + force-push to the **feature branch only** (never `main`), but ONLY after an
explicit human approval phrase AND a freshly-run green `loop-harness`.

## What Changes

- **New durable behaviour B32 (release-automation): `loop-final` review-approved finalisation.**
  (B31 is claimed by the in-flight `make-always-background` change / PR #58; this change is B32.)
  When the human approves an open PR (approval phrase such as "PR looks great" / "looks good" /
  "approved to finalize"), the agent MAY run `make loop-final BRANCH=<feat/...>`, which:
  1. Verifies a human approval was given (explicit flag `APPROVED=1`, set only on human approval).
  2. Runs a FRESH `make loop-harness` and requires it GREEN (B20 pre-flight) before any rewrite.
  3. Runs `squash-commits` (one typed Conventional commit) — the B28a/B30b guard is bypassed
     ONLY under this approved path.
  4. Regenerates the CHANGELOG from the squashed commit (`changelog` + `bump-from-changelog` +
     `changelog-format`).
  5. `git push --force-with-lease` to the SAME feature branch (never `main`).
- **B28a / B30b keep their default force:** without the approval gate, squash/force-push on an
  open PR remains forbidden. `loop-final` is the ONLY sanctioned squash+force path, and only post-approval.
- **B30a stays absolute:** `git revert` is still never allowed. Force is `--force-with-lease` only.
- All 6 B8 sync docs (AGENTS.md, hermes/skills/openspec-loop-harness.md,
  docs/openspec-engineering-loop-harness.md, Makefile, scripts/run-loop-harness.sh, e2e harness)
  updated to describe B31 identically and bump the behaviour range.

## Capabilities

- `release-automation`: adds the review-approved `loop-final` finalisation flow.

## Impact

- Affected: `Makefile` (new `loop-final` target + guard), `AGENTS.md`, the skill mirror, the docs
  reference, `scripts/run-loop-harness.sh` (range), and the B8 doc-sync checker expectations.
- No generated TS changes. `make check-docs-sync` must stay green with the new behaviour range.
