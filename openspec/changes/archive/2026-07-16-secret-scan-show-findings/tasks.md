# Tasks: surface secret-scan findings + best-practice working-tree scan

## Root cause (why this change exists)
`make loop-secret-scan` only printed "secrets detected -- loop blocked" — the operator
could NOT see which file/rule fired. Also gitleaks was run in git-history mode (`detect`
without `--no-git`), which only scans *committed* history, so a staged-but-uncommitted
`password.txt` was never even checked. Default gitleaks also misses low-entropy
`PASSWORD='...'` assignments, which is why a repo-local rule was added.

## Tasks
- [x] 1. Change `docker-compose-files/gitleaks.yaml` to run `detect --no-git` over the
      whole working tree and emit a JSON report (`--report-format=json
      --report-path=/src/.gitleaks-report.json`).
- [x] 2. Rewrite the `loop-secret-scan` Makefile target to read the JSON report and print
      each finding as `file | rule | line` (redacted) before failing closed.
- [x] 3. Add `.gitleaks-report.json` to `.gitignore` (scan artifact, never committed).
- [x] 4. Extend `scripts/secret_scanner.py`: `scan_text`/`scan_file` accept an optional
      `config` arg so callers scan with the repo `.gitleaks.toml` (real rule coverage).
- [x] 5. Add repo-local gitleaks rule `repo-password-assignment` in `.gitleaks.toml`
      (default ruleset + tight low-entropy assignment rule; RE2-compatible, no lookaheads).
- [x] 6. Add real, no-mock integration tests:
      `test_repo_password_rule_fires_on_low_entropy_assignment` and
      `test_repo_password_rule_ignores_env_var_and_empty` (drive REAL gitleaks with the
      repo `.gitleaks.toml`).
- [x] 7. `openspec validate secret-scan-show-findings` passes.
- [x] 8. `make check-docs-sync` (B8) passes — no stage-order change, only target internals.
- [x] 9. `pytest tests/test_secret_scanner_integration.py` passes (real gitleaks on host).
- [x] 10. `make loop-secret-scan` now FAILS CLOSED on `password.txt` AND prints the file/rule/line.
