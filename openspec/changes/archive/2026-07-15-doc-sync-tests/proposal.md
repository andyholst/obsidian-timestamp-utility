# Change: doc-sync-tests

## Why
The B8 doc/loop-sync gate (`scripts/check-docs-sync.py`, added in `doc-sync-gate`) is the
enforcement behind "the sync docs never drift". But a gate that is only ever run on the
*current* tree can give a false sense of safety: we had a normalization bug where the
`b_range_ok` check stripped parentheticals and silently missed a `B1-B21` vs `B1-B25`
drift in the Makefile. We need a hermetic test suite that proves the gate's *semantics* —
that it correctly PASSES aligned files and FAILS each specific misalignment — using real
copies of the sync files in aligned / drifted states as fixtures. We also need the gate's
own unit tests to run at the very start of `loop-harness` so a broken gate or a drifted
doc fails before any heavy stage spins up.

## What Changes
- Add `tests/test_check_docs_sync.py` — hermetic pytest suite that loads `check-docs-sync.py`
  and asserts its verdicts against fixture "backup" copies of the 5 sync files
  (`Makefile`, `AGENTS.md`, `hermes/skills/openspec-loop-harness.md`,
  `scripts/run-loop-harness.sh`, `docs/openspec-engineering-loop-harness.md`) in:
  - `in_sync` / `in_sync_ascii` / `in_sync_en_dash` — all aligned → PASS (glyph-tolerant)
  - `drift_missing_ts_floor` — Makefile drops `loop-ts-floor` from its chain → FAIL (Makefile)
  - `drift_b_range_low` — AGENTS.md `B1-B21` instead of `B1-B25` → FAIL (AGENTS.md B-range)
  - `drift_reorder` — AGENTS.md secondary chain mention reordered; canonical chain still
    present elsewhere → PASS (guards against false positives)
- Fixtures live under `tests/fixtures/check_docs_sync/<scenario>/` as real copies of the
  sync files (mirroring repo layout) with only the targeted drift applied.
- Add `make test-check-docs-sync` (host-runnable, no docker/Ollama) and
  `make check-docs-sync-and-test`.
- Wire `make test-check-docs-sync` + `make check-docs-sync` as **PRE-FLIGHT 0** at the start
  of `scripts/run-loop-harness.sh` (and `make loop-harness`), so the gate proves it behaves
  and the tree proves it is in sync before any stage runs.

## Capabilities
- **Modified Capabilities**: `doc-sync` (extend the existing gate spec with a requirement
  that the gate has hermetic unit tests asserting pass/fail semantics against fixture files,
  and that those tests run as the first step of `loop-harness`).

## Impact
- No generated TS / Python agent behaviour changes. Tests + fixtures + Makefile target +
  runner pre-flight only. `make loop-harness` now fails fast if the gate logic is broken or
  a sync doc has drifted.
