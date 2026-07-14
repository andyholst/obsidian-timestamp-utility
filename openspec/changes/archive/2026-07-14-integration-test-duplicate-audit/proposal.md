# Proposal: Integration Test Duplicate Audit

## Why
The `agents/agentics/tests/integration/` suite has grown to **31 files / 193 test
functions**. B17 (loop-integration rules) rule #1 states: *"No dead tests. When a file
is a strict duplicate of another (or superseded by a canonical per-agent file), DELETE
the duplicate — never keep two files asserting the same thing."* A prior audit already
removed the `test_jest_execution_*` trio. We have not yet audited the remaining 31 files
for strict duplicates (same imports + same assertions = redundant) versus the 82-test
fast loop subset (`-m "integration and not e2e and not slow"`).

The goal is NOT to delete necessary coverage. The non-slow 82 tests exercise agentic
behaviour (error recovery, config, agent composer, npm tools, phase1–4 orchestration,
cross-validation, immutable state, base agent) that neither unit tests nor the 4 e2e
gates cover. Only *strict* duplicates and genuinely superseded files should be removed.

## What Changes
- Add a `specs/integration-test-hygiene/spec.md` describing the duplicate-audit
  requirement and the keep/delete decision rules.
- Run a mechanical duplicate-detection pass across all 31 integration test files.
- For each pair flagged as a strict duplicate (identical target module + identical
  assertion set), DELETE the redundant file (keeping the canonical one).
- Update `loop-tasks` / inventory so the remaining suite is documented as non-duplicate.
- Re-run `make loop-integration` (fast subset) to prove the trimmed suite is still green.

## Capabilities
- `integration-test-hygiene` — the suite must contain no two files that are strict
  duplicates of each other (same imports and same assertion targets).

## Impact
- Files: `agents/agentics/tests/integration/*.py` (read; deletions only where strict
  duplicate confirmed). No production `src/` change.
- Loop: `loop-integration` stays green at ~6 min (82 non-slow tests); full
  `make test-agents-integration` (incl. `slow` + e2e) stays the deep-verify target.
- Risk: low — deletions are limited to proven strict duplicates; necessary coverage is
  preserved.
