# Proposal

## Why
When the OpenSpec loop-harness reaches a GREEN state (all loop gates pass: collect, unit, unit-real,
e2e, integration, build-app, test-app), the staged work should be finalised automatically and safely:
the many intermediate worktree/branch commits are squashed into ONE typed Conventional commit, the
changelog is regenerated (nothing omitted, markdown-clean), and the version is bumped. Today this is a
manual, easy-to-forget, error-prone sequence the user must drive by hand.

## What Changes
- Define a `make loop-finish` (or extend `make release-flow`) stage that, ONLY when the loop gate is
  green, performs in order: `squash-commits` (typed, commitlint-gated) -> `changelog` (append, no
  omissions, formatted) -> `bump-from-changelog` (version + tag) -> `changelog-format`.
- The squash/changelog/bump MUST be gated on the loop being green (never on a red gate).
- Document this end-state behaviour in AGENTS.md and the `openspec-loop-harness` skill (B8 sync) so
  the harness/loop-agent skill instructs: "when green, squash + changelog + bump; verify nothing
  omitted and linted/formatted".

## Capabilities
- `release-automation` (loops `loop-finish` / `release-flow` into the green-gated sequence).

## Impact
- A green loop-harness reliably ends with a single squashed commit, a complete + clean changelog, and
  bumped Obsidian version files — with no push (B14).
