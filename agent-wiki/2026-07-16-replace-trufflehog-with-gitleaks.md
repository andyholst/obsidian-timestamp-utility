# replace-trufflehog-with-gitleaks — Work Log

**Date:** 2026-07-16
**OpenSpec Change:** `replace-trufflehog-with-gitleaks`
**Branch:** `fix-truffle-hog-issue`

## Summary
Replaced the broken TruffleHog GitHub Action (which failed on invalid action inputs and a BASE==HEAD abort, blocking every push/PR) with gitleaks — the de-facto open-source secret scanner. The change swaps `trufflehog.yml` for a gitleaks CI workflow, adds a local fail-closed `pre-commit`/`commit-msg` hook wired to a Python engine (`scripts/secret_scanner.py`) that delegates 100% of detection to gitleaks, ships container images plus a `.gitleaks.toml`, and ships 28 hermetic/integration tests that exercise the real gitleaks binary.

## Verification Against Spec
- Requirement "Replace the broken TruffleHog Action with gitleaks": `trufflehog.yml` rewritten to `gitleaks/gitleaks-action@v2` with `fetch-depth: 0` + `GITLEAKS_CONFIG=.gitleaks.toml` (tasks 1.1/1.2); no `trufflesecurity/trufflehog` reference remains; `openspec validate` reports the change valid ✅
- Requirement "Pre-commit hook blocks secrets in staged content": `git-hooks/pre-commit` invokes `python3 scripts/secret_scanner.py --staged` before the trailing-whitespace fix (task 4.1); real-secret / clean / allowlisted-token scenarios backed by integration tests (3.2) and `make scan-staged` green (6.4) ✅
- Requirement "commit-msg hook blocks secrets in the commit message": `git-hooks/commit-msg` invokes `secret_scanner.py --message-file` after the commitlint check (task 4.2); clean-message and secret-message flows verified; commitlint still runs ✅
- Requirement "A Python secret-scanner engine that delegates 100% to gitleaks": `scripts/secret_scanner.py` implements `scan_text`/`scan_file`/`scan_staged_content`/`scan_commit_message`/`scan_repo`, returns a structured `ScanResult`, prefers the gitleaks container image and falls back to a local binary (`GITLEAKS_RUNTIME=none|false|0` forces binary, tasks 2.1–2.4); absent-gitleaks path returns `engine="unavailable"` (fail-closed) ✅
- Requirement "Tests cover happy, negative, and integration paths with the real gitleaks binary": `tests/test_secret_scanner.py` (16 hermetic) + `tests/test_secret_scanner_integration.py` (12, real binary, no mocks on detection) run → 28 passed (task 3.3); integration suite skips cleanly when no binary is present, matching the spec ✅
- Caveat from `openspec status`: the `design` artifact is still unticked (Progress 3/4: proposal ✅, design ⬜, specs ✅, tasks ✅); the design decisions are fully documented inside `tasks.md` §Design decisions and every task is ticked.

## Key Decisions
- Chose gitleaks rather than patching TruffleHog because the defect lived in the *Action wrapper* (unsupported `verified_only`/`ignore_paths` inputs + BASE==HEAD abort), not detection quality; gitleaks as a `pre-commit`/`commit-msg` hook catches secrets locally before they ever reach history, satisfying the "validate commit message pre-commit" requirement.
- Engine delegates 100% to gitleaks with no homemade regex/entropy detector, so future secret patterns are a `.gitleaks.toml` config change (extends default ruleset via `useDefault = true` + repo allowlist for fixtures/docs/caches/`.env`), never a code rewrite.
- Container-first / binary-fallback runtime (`GITLEAKS_RUNTIME=none|false|0` forces binary) keeps the loop harness portable while still exercising real gitleaks inside `containers/gitleaks-tests` via compose.
- Hooks invoke `python3` only (never `git commit`), so they stay inert during `make loop-*` (B4/B14), consistent with the existing trailing-whitespace hook.

## Current Status
Complete — all five spec requirements are implemented and verified (`openspec validate` valid, 28 tests pass, `make check-secrets`/`scan-staged` green); the sole open item is the unticked `design` artifact in `openspec status` (3/4).

## Recommended Next Steps
- Tick the `design` artifact in `openspec/changes/replace-trufflehog-with-gitleaks/` so `openspec status` reads 4/4 (content already captured in `tasks.md`), then run `make phase7-archive CHANGE=replace-trufflehog-with-gitleaks`.
- None beyond that — archive.
