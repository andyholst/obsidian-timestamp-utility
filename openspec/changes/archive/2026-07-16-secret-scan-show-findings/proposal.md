# Proposal: surface secret-scan findings + best-practice working-tree scan

## Why
The mandatory `loop-secret-scan` stage was opaque ("secrets detected -- loop blocked")
and, worse, only scanned **committed git history** (`detect` without `--no-git`), so a
staged-but-uncommitted `password.txt` (with `PASSWORD='...'`) was never even checked.
The default gitleaks ruleset also misses low-entropy credential assignments. The operator
could not tell what the scanner caught.

## What Changes
- **Visibility:** the `loop-secret-scan` stage now writes the gitleaks JSON report and
  prints each finding as `file | rule | line` (redacted) before failing closed.
- **Best-practice scan:** switched to `detect --no-git` over the whole working tree
  (uncommitted files included), still containerized via compose. This is the gitleaks
  recommended way to scan the working tree, and it honors `.gitleaks.toml` allowlists.
- **Sensitivity:** extended the default ruleset with a tight repo-local rule
  `repo-password-assignment` (RE2-compatible, entropy 0) that catches low-entropy
  `PASSWORD=/SECRET=/API_KEY=` assignments the default ruleset misses — without
  false-positiving on `${VAR}` refs, empty values, or `os.getenv(...)` calls.
- **Wrapper fix:** `secret_scanner.py` `scan_text`/`scan_file` now accept a `config` arg
  so tests exercise the real repo ruleset.

## Capabilities
- `loop-secret-scan` (extends the existing secret-scanning discipline)

## Impact
- Only the loop secret-scan path, `.gitleaks.toml`, the Python wrapper, and tests change.
- No generated TS / agentic behaviour affected.
- Nothing committed/pushed (B4/B14) — verification only.
