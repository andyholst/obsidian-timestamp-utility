# Proposal: openspec-scaffold-help

## Why

The OpenSpec scaffolding harness (`scripts/scaffold-openspec-change.sh` + `make openspec-new`)
was created in change `openspec-scaffold-make`, but its help/usage was thin: `make openspec-new`
with no `NAME` printed a one-line error, not the documented arguments + example. The user asked
for clear help showing how to pass arguments and a worked example. This change adds a full
`usage()` to the script and makes `make openspec-new` (no NAME) print it, then verifies the
behaviour end-to-end through `make`.

## What Changes

- `scripts/scaffold-openspec-change.sh`: richer `usage()` (SYNOPSIS / ARGUMENTS / two worked
  EXAMPLES / RESULT / NOTES); `--help`/`-h` prints it; missing `--name` prints the error + usage.
- `Makefile` `openspec-new`: when `NAME` is empty, print the script's `--help` (with examples)
  instead of a bare error.
- Add a verifiable task that proves the help path works by actually invoking `make openspec-new`
  with no NAME and asserting the usage text appears.

## Capabilities

- `openspec-scaffold-help` (new): documented, verifiable help for the OpenSpec scaffolding harness.

## Impact

- No change to the loop-harness gates or the deterministic floor.
- No git commit/push (B4/B14).
