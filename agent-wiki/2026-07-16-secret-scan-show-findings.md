# secret-scan-show-findings — Work Log

**Date:** 2026-07-16
**OpenSpec Change:** `secret-scan-show-findings`
**Branch:** `fix-truffle-hog-issue`

## Summary
The change made the `loop-secret-scan` loop stage transparent and switched it to a best-practice working-tree scan. Previously the stage only printed "secrets detected -- loop blocked" and ran gitleaks in git-history mode (`detect` without `--no-git`), so staged-but-uncommitted secrets were never checked and the operator couldn't see what fired. It now emits a gitleaks JSON report, prints each finding as `file | rule | line` (redacted) before failing closed, scans the whole working tree via `detect --no-git`, and adds a tight `repo-password-assignment` rule for low-entropy `PASSWORD=/SECRET=/API_KEY=` assignments the default ruleset misses.

## Verification Against Spec
- Requirement "secret-scan reports which file/rule fired": verified — tasks 1–2 rewrote `docker-compose-files/gitleaks.yaml` to emit `--report-format=json` and the `loop-secret-scan` Makefile target reads that report and prints each finding as `file | rule | line`; task 10 confirms `make loop-secret-scan` FAILS CLOSED on `password.txt` AND prints file/rule/line; `openspec validate secret-scan-show-findings` reports the change is valid ✅
- Requirement "working-tree scan is best-practice gitleaks": verified — task 1 switched to `detect --no-git` over the whole working tree (uncommitted files included, containerized); task 5 added `repo-password-assignment` on top of `[extend] useDefault = true`; task 6 integration tests (`test_repo_password_rule_fires_on_low_entropy_assignment`, `test_repo_password_rule_ignores_env_var_and_empty`) drive REAL gitleaks with `.gitleaks.toml` and confirm the rule fires on low-entropy assignment yet ignores `SECRET=${VAR}`, empty `PASSWORD=`, and `API_KEY=os.getenv('X')`; task 9 `pytest tests/test_secret_scanner_integration.py` passes; task 10 confirms a staged-but-uncommitted `password.txt` is caught ✅

## Key Decisions
- Switched from git-history mode (`detect` without `--no-git`) to `detect --no-git` over the entire working tree — gitleaks' recommended way to scan the working tree, so staged-but-uncommitted secrets (the original blind spot) are now caught.
- Used `[extend] useDefault = true` (never hand-rolled detection) plus ONE tight repo-local rule `repo-password-assignment` (RE2-compatible, entropy 0, no lookaheads) — avoids false positives on `${VAR}` refs, empty values, and `os.getenv(...)` calls.
- `secret_scanner.py` `scan_text`/`scan_file` now accept an optional `config` arg so the wrapper's tests exercise the REAL repo ruleset rather than a mock.
- Added `.gitleaks-report.json` to `.gitignore` so the scan artifact is never committed (B4/B14 hygiene).
- Kept `make check-docs-sync` green (task 8) — only target internals changed, no stage-order change, so the B8 sync set stays consistent.

## Current Status
Complete — `openspec validate` passes, all 10 tasks ticked, and the real-gitleaks integration tests are green. (Note: the optional `design.md` artifact was intentionally not authored; it is not required for this change.)

## Recommended Next Steps
- None — archive. Run `make phase7-archive CHANGE=secret-scan-show-findings` to merge the spec into `openspec/specs/` (no git commit/push, per B4/B14).
