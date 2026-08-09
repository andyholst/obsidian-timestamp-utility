# Makefile Verification

## Why

The project has 80+ make targets across build, test, lint, release, loop-harness, and OpenSpec workflows. No single systematic verification exists to confirm every target works correctly. We need a comprehensive test pass that exercises each target and documents results.

## What Changes

- Systematically run every make target in the Makefile
- Verify each target exits cleanly or produces expected output
- Document any failures, warnings, or unexpected behavior
- Create an OpenSpec change with tasks tracking each verification step

## Capabilities

- **makefile-verification**: Every make target is tested and verified against expected behavior

## Impact

- Low risk — only reads files and runs commands
- Affects all developers who use the Makefile
- No code changes required
