# squash-override-flag Specification

## ADDED Requirements

### Requirement: Explicit ALLOW_SQUASH override for the pre-PR squash guard
The `squash-commits` target MUST honour an `ALLOW_SQUASH=1` environment flag that deliberately
bypasses the B28a/B30b pre-PR guard, while keeping the safe default intact and never allowing revert.

#### Scenario: override set on an open PR
- **WHEN** the user runs `make squash-commits ALLOW_SQUASH=1` on a branch that is an open PR / pushed branch
- **THEN** the guard is bypassed, a loud WARNING is printed ("rewrites history — you asked"), and the
  squash proceeds — but revert is still forbidden (B30a)

#### Scenario: override unset on an open PR (default)
- **WHEN** the user runs `make squash-commits` (no `ALLOW_SQUASH`) on an open/pushed PR branch
- **THEN** the target refuses (fail closed), prints the SQUASH FORBIDDEN message, and suggests
  `ALLOW_SQUASH=1` as the explicit escape hatch

#### Scenario: override unset on a local pre-PR branch
- **WHEN** the user runs `make squash-commits` on a local branch with no open PR
- **THEN** squash is allowed (pre-PR), exactly as before B30d
