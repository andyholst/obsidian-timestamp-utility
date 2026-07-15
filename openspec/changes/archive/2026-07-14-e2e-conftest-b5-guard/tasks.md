# Tasks — e2e-conftest-b5-guard

## 1. Diagnose (audit finding)
- [x] 1.1 Reproduce: running greetings e2e with `PROJECT_ROOT=<real repo>` deleted the real `src/`
      (B5/B6 violation). Confirmed via `git status` + `ls`.
- [x] 1.2 Root cause: conftest `shutil.rmtree(_dst_src)` at the real `src/`; the B3 guard only
      covered the agentics mount, not the real repo root. Same-file `copy2` raised `SameFileError`.

## 2. Fix (B13 — floor defect, fix Python not the spec)
- [x] 2.1 Extract pure predicate `_e2e_may_copy_real_src(project_root, real_src, agentics_src_mount)`.
- [x] 2.2 Conftest only rmtree+copies when the predicate is True (isolated temp dir).
- [x] 2.3 Guard the `package.json`/`tsconfig.json`/`jest.config.js`/`manifest.json` copy loop
      against same-file copies.
- [x] 2.4 Restore the deleted `src/` files from HEAD (B5).

## 3. Tests
- [x] 3.1 Add `tests/unit/test_e2e_conftest_b5_guard_unit.py` (5 cases): refuses real repo root,
      real src exactly, agentics mount, `/app`; allows isolated temp dir.
- [x] 3.2 Confirm greetings e2e now runs GREEN with OLLAMA_HOST set + isolated temp dir, and the
      real committed `src/` is INTACT afterward (verified `src/main.ts` 9790 B, git clean).

## 4. Verification
- [x] 4.1 `pytest tests/unit/test_e2e_conftest_b5_guard_unit.py` = 5/5 green.
- [ ] 4.2 Full `tests/unit/` = 100% green (run after conftest change).
- [x] 4.3 `openspec validate e2e-conftest-b5-guard` clean.

## 5. Document + archive
- [x] 5.1 `design.md` not required (harness-floor change); proposal + spec + tasks suffice.
- [x] 5.2 Update `agent-wiki/2026-07-14-e2e-conftest-b5-guard.md` with Verification Against Spec.
- [x] 5.3 `openspec archive e2e-conftest-b5-guard` (spec-only merge).
- [x] 5.4 Update `agent-wiki/index.md`.
