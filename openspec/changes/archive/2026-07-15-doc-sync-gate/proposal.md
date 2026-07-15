# Change: doc-sync-gate

## Why
B8 declares "the four artifacts are ONE source of truth — never let them drift" — but it is a
**manual discipline with no enforcement**. The `loop-ts-floor` stage added in the
`strict-ts-test-floor` change was mirrored into Makefile / AGENTS.md / the skill / the runner, but
`docs/openspec-engineering-loop-harness.md` (which B8 itself names as the authoritative reference)
was NOT updated and still claims "SEVEN stages" with no `loop-ts-floor`. Nothing caught it. We
need a gate that fails when any B8 doc drifts, and that explains the drift in plain language via
the project-manager Hermes CLI scoped to the current path.

## What Changes
- New `scripts/check-docs-sync.py`: canonical-token comparison across all B8 sync files (Makefile,
  AGENTS.md, `hermes/skills/openspec-loop-harness.md`, `scripts/run-loop-harness.sh`, and
  `docs/openspec-engineering-loop-harness.md`). Tokens: the exact 8-stage order string (with
  `loop-ts-floor`), the `loop-ts-floor` token, and the B-behaviour range upper bound (B25).
- New `make check-docs-sync` target; wired into `loop-collect` so drift fails the hermetic pre-flight.
- On drift, the script invokes `hermes profile use project-manager` then `hermes -z "<prompt>"`
  with `cwd` = the directory it was run from (per-path scoping), and still exits non-zero.
- Fix the drifted `docs/openspec-engineering-loop-harness.md` (7→8 stages, add `loop-ts-floor`).

## Capabilities
- `doc-sync`

## Impact
- No generated TS / Python agent behaviour changes. Docs only + one new check script + Makefile target.
- `make loop-collect` now also runs `check-docs-sync`; a doc drift turns the whole loop red (B8
  enforced, not advisory).
