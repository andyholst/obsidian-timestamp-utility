# Proposal: squash-override-flag (B30d — explicit ALLOW_SQUASH override)

## Why
The user confirmed the no-squash / no-revert rule (B28/B30): `squash-commits` must refuse on any
open or pushed PR. But there are legitimate moments where the human deliberately wants to squash a
PR branch anyway (e.g. a pre-merge cleanup the reviewer agreed to). The rule should be enforceable
by default yet **overridable on explicit demand** — never silent.

## What Changes
- **B30d (new durable behaviour):** `make squash-commits ALLOW_SQUASH=1` deliberately bypasses the
  B28a/B30b pre-PR guard. OFF by default. When set it ALWAYS prints a loud WARNING that history is
  being rewritten on the user's explicit say-so. It does NOT bypass B30a (revert is still never
  allowed — this only governs squash).
- The default (no flag) is unchanged: refuse on any open PR / pushed branch, fail-open only when
  `gh`/token is absent.

## Capabilities
- `pr-fix-no-revert` (extended): adds the `ALLOW_SQUASH=1` override sub-behaviour (B30d).

## Impact
- Must NOT regress B28a, B30a, B30b, or the loop-harness gates. The override is opt-in and loud;
  the safe default is preserved.
