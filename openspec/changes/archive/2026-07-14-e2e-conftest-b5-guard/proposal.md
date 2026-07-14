# E2E conftest B5/B6 guard (never delete the real committed src/)

## Why
During a harness/loop-engineering audit (re-verifying completed OpenSpec tasks against the
B-rules in AGENTS.md), running the greetings e2e with `PROJECT_ROOT` pointed at the **real repo
root** caused `tests/integration/conftest.py` to `shutil.rmtree(_dst_src)` the REAL plugin `src/`
(line 69 of the pre-fix code). The e2e then left `src/main.ts`, `src/__tests__/main.test.ts`,
`src/taskProcessor.ts`, `src/folderSelectorModal.ts`, `src/__mocks__/obsidian.ts`, and two test
files **deleted from disk** — a direct B5/B6 violation (the harness must restore the committed
baseline, never destructively delete it). The same-file `copy2` loop also raised `SameFileError`
when `PROJECT_ROOT` equaled the real repo root.

Root cause: the conftest's "copy real src into PROJECT_ROOT" logic was only guarded against the
agentics *source mount* (`/app`, `agents/agentics/src`), not against `PROJECT_ROOT` being the real
plugin repo root. That is a latent harness defect — any run pointed at the real repo nukes the
baseline.

## What Changes
- Extracted a pure, testable predicate `_e2e_may_copy_real_src(project_root, real_src,
  agentics_src_mount)` that returns False when the destination would be the real committed `src/`
  or the agentics mount (so generation stays in an ISOLATED temp dir only).
- The conftest now calls the predicate; it only rmtree+copies when safe (isolated temp dir).
- Guarded the `package.json`/`tsconfig.json`/`jest.config.js`/`manifest.json` copy loop against
  same-file copies (skips when `PROJECT_ROOT` === real repo root).
- Added hermetic unit tests `test_e2e_conftest_b5_guard_unit.py` (5 cases) covering the predicate.

## Capabilities
- `e2e-conftest-b5-guard` (new) — the e2e harness never deletes/copies into the real committed src.

## Impact
- Scope: `tests/integration/conftest.py` + new unit test. No pipeline/production agent changed.
- No generated TS authored in Python (B10 holds). The fix is a harness-floor safety guard (B13).
