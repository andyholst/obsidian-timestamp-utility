# 2026-07-15-doc-sync-tests

## OpenSpec Change
`doc-sync-tests` (archived as `2026-07-15-doc-sync-tests`).

## Branch
`enhance-squash-commits` (working tree, NOT committed — B4/B14).

## Why
The B8 doc/loop-sync gate (`check-docs-sync`) enforces that the loop-harness stage order,
the `loop-ts-floor` guard, and the B-behaviour range stay in agreement across the 5 B8
"source of truth" files (Makefile, AGENTS.md, hermes skill, `run-loop-harness.sh`,
harness doc). The gate itself was previously tested with **hardcoded constants** — every
evolution (B26, a new stage) meant manual maintenance, and a deleted make command slipped
through. We needed the gate's contract to **derive from the source of truth** and the
**negative tests** to prove it REACTS (RED) when a B-step / stage / make-target is removed
from ANY of the sync files.

## What Changed
- **`scripts/check-docs-sync.py`** — contract now DERIVED (no hardcoded constants):
  - stage order parsed from `scripts/run-loop-harness.sh` `STAGES=(...)`;
  - B-range upper bound = max `B\d+` across the narrative `.md` docs.
  - NEW `missing_make_targets()`: every canonical stage MUST exist as a real `name:` Makefile
    target — catches a *deleted make command* (target gone, chain comment remains).
- **`scripts/regen_doc_sync_fixtures.py`** (new, committed) — rebuilds the `.md` fixtures
  from the CURRENT real docs; drift anchors DERIVED (`_derive_b_range_drift` lowers the
  current max-B; anchor-check fails loudly if a doc restructure drops the phrase).
- **`tests/test_check_docs_sync.py`** — fixtures are REAL literal copies of the 3 sync `.md`
  files (no Makefile/runner/scripts copies); added per-file NEGATIVE discrimination tests
  covering all 5 sync files; semantic-accuracy bar >= 95% (held at 100%).
- **`Makefile`** — `b9-perms` wired as a PREREQUISITE of `test-check-docs-sync` +
  `regen-doc-sync-fixtures` (rootless-nerdctl world-read floor can't be skipped).
- **`scripts/run-loop-harness.sh`** — PRE-FLIGHT 0 (check-docs-sync unit tests + live gate)
  runs FIRST and `exit 1` aborts the whole loop before any stage if red.

## Verification Against Spec
Per `openspec/specs/doc-sync/spec.md` (archived merge):
- **Gate derives contract from source of truth** — PASS: stage order from runner STAGES,
  B-range from max-B in docs; adding B26 needs only `make regen-doc-sync-fixtures`, no
  constant edit.
- **RED when a B-step is removed (negative test)** — PASS: `test_b_range_low_red_when_any_single_file_drifts`
  + `test_stage_removed_red_when_any_single_file_drifts` go RED and name exactly the offending
  file for AGENTS.md / hermes skill / harness doc.
- **RED when a make target is removed** — PASS (proven by probe): deleting `loop-e2e:` from
  the Makefile → `DRIFT in Makefile: missing make target(s): loop-e2e`. Before the fix the gate
  silently passed.
- **No false positives** — PASS: `drift_reorder` (secondary mention only) stays GREEN;
  `test_make_target_present_stays_green` confirms a fully-aligned Makefile is silent.
- **PRE-FLIGHT 0 fires first** — PASS: `run-loop-harness.sh --hermetic` prints PRE-FLIGHT 0 at
  line 1, `PRE-FLIGHT 0 PASS` at line 15, THEN stages run (loop-collect/loop-ts-floor/loop-unit
  all PASS, loop_exit=0).

Real test runs:
```
make test-check-docs-sync (container)   -> 33 passed, exit 0
make regen-doc-sync-fixtures            -> exit 0 (rebuild + verify)
host pytest test_check_docs_sync.py     -> 33 passed, semantic accuracy 6/6 = 100%
make check-docs-sync (live)             -> PASS
openspec validate doc-sync-tests        -> valid
```

## Key Decisions
- Fixtures are REAL literal copies of the 3 `.md` sync files only — never copies of the
  Makefile / runner / gate script (per user rule). The gate's other 2 sync files are layered
  in fresh per test so the `.md` drift is isolated.
- Drift anchors are DERIVED from the live doc + shared via the regen module so the test and
  the fixture builder can never disagree (single source of truth).
- B9 perms enforced by `b9-perms` as a Makefile prerequisite, not by memory — fixes the
  repeated "agent writes `-rw-------`, container can't read it" failure.

## Current Status
Change archived (spec merged into `openspec/specs/doc-sync/spec.md`, +2 requirements).
Working-tree edits (`scripts/check-docs-sync.py`, `scripts/regen_doc_sync_fixtures.py`,
`tests/test_check_docs_sync.py`, `Makefile`, `scripts/run-loop-harness.sh`, fixtures) are
NOT committed (B4/B14) — deliberate human step.

## Recommended Next Steps
- Human: review + commit the working-tree changes (the derived-contract gate + the per-file
  negative tests + B9-perms wiring).
- Optionally run the FULL `make loop-harness` on the host (docker/nerdctl/Ollama) to exercise
  the non-hermetic stages (loop-unit-real / loop-e2e / loop-integration / loop-build-app /
  loop-test-app); PRE-FLIGHT 0 + hermetic stages already proven green.
