# e2e-conftest-b5-guard — Work Log

**Date:** 2026-07-14
**OpenSpec Change:** `e2e-conftest-b5-guard`
**Branch:** `setup-loop-harness-openspec`

## Summary
A harness/loop-engineering audit (re-verifying completed OpenSpec tasks against the B-rules in
AGENTS.md + the Hermes skill) surfaced a **real B5/B6 violation** in the e2e harness: running the
greetings e2e with `PROJECT_ROOT` pointed at the real repo root caused `tests/integration/conftest.py`
to `shutil.rmtree` the REAL plugin `src/` — deleting `src/main.ts`, `src/__tests__/main.test.ts`,
and 4 other TS files from disk. The B3 guard only covered the *agentics source mount*, not the
real repo root. This is a latent floor defect (B13 — fix the Python floor, not the spec).

## Tasks Completed
- Extracted a pure, testable predicate `e2e_may_copy_real_src(project_root, real_src,
  agentics_src_mount)` into a side-effect-free module `tests/integration/_e2e_guard.py`.
- Conftest now only rmtree+copies when the predicate is True (isolated temp dir only).
- Guarded the `package.json`/`tsconfig.json`/`jest.config.js`/`manifest.json` copy loop against
  same-file copies (`SameFileError`).
- Added `tests/unit/test_e2e_conftest_b5_guard_unit.py` (5 hermetic cases).
- **Fixed a contamination bug of my own:** the first version of the guard test imported
  `tests.integration.conftest` at module level, which executes the conftest's import-time side
  effects and broke 5 `test_collaborative_generator` tests in the full suite. Moved the predicate
  to the side-effect-free `_e2e_guard` module and import from there — contamination gone (36/36
  green together).
- Restored the deleted `src/` from HEAD (B5).

## Verification Against Spec
| Requirement | Result |
|---|---|
| E2E harness never deletes the real committed source | PASS — predicate returns False for real repo root / real src / agentics mount; 5/5 guard tests |
| E2E harness guards same-file copies | PASS — copy loop skips same-file |
| Greetings e2e green + real src intact | PASS — ran with OLLAMA_HOST + isolated temp dir: 1 passed in ~80s; `src/main.ts` 9790 B, git clean after |
| Full unit suite | PASS — **522 passed** (517 prior + 5 new), 0 failed |

## Key Decisions
- **B5/B6 is a hard invariant:** the e2e harness must READ the committed baseline, never delete it.
  The conftest now refuses to copy into the real `src/` regardless of `PROJECT_ROOT`.
- **B13 floor fix:** this was a harness defect, fixed in Python (the guard), not by editing spec
  TS bodies (B10/B11 respected).
- The e2e MUST be run with an ISOLATED temp `PROJECT_ROOT` (its default `/tmp/obsidian-project`) and
  never pointed at the real repo root.

## Current Status
Change complete and verified. Ready for `openspec archive e2e-conftest-b5-guard` (spec-only merge).
Commit/push is a deliberate human step (B4/B14).

## Recommended Next Steps
- Optionally add a pytest-level assertion in CI that `src/main.ts` exists + is unchanged after the
  e2e run (belt-and-suspenders for B5).
- Consider documenting in AGENTS.md Phase 6 that `PROJECT_ROOT` must be an isolated temp dir for
  e2e runs (this is the trap that triggered the deletion).
