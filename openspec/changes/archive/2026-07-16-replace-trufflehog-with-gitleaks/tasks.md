# Tasks: Replace TruffleHog with gitleaks

## Design decisions (implemented)
- **gitleaks is the ONLY secret scanner.** No homemade regex/entropy detection — the wrapper
  delegates 100% of detection to gitleaks (local binary, or a gitleaks container image when a
  container runtime is present). This removes the broken TruffleHog Action and the unmaintained
  custom-detector approach.
- **Container-first, binary fallback.** `scripts/secret_scanner.py` prefers a container image
  (`containers/gitleaks/Dockerfile` → `zricethezav/gitleaks:v8.18.4`) via nerdctl/docker, and
  falls back to a local `gitleaks` binary (`GITLEAKS_BIN`). `GITLEAKS_RUNTIME=none|false|0`
  forces binary mode.
- **One ruleset everywhere.** `.gitleaks.toml` uses `[extend] useDefault = true` plus repo-local
  allowlists (test fixtures, docs, dependency/build caches, `.env`/`.git`). Local hooks, `make
  check-secrets`, and CI all run the same engine + config.

## Implementation
- [x] 1.1 Replace `.github/workflows/trufflehog.yml` with a gitleaks workflow (`gitleaks/gitleaks-action@v2`, `fetch-depth: 0`, `GITLEAKS_CONFIG=.gitleaks.toml`). No unsupported inputs.
- [x] 1.2 Add `.gitleaks.toml` (extend default rules, allowlist test fixtures / docs / caches / .env).
- [x] 2.1 Implement `scripts/secret_scanner.py` with `scan_text`, `scan_file`, `scan_staged_content`, `scan_commit_message`, `scan_repo` entry points.
- [x] 2.2 Engine prefers a gitleaks container image (nerdctl/docker) and falls back to a local gitleaks binary; `GITLEAKS_RUNTIME=none|false|0` forces binary mode. No builtin detector.
- [x] 2.3 Return a structured `ScanResult` (clean, findings[{rule, match, line, file, severity}], engine) usable by hooks and tests.
- [x] 2.4 Build the gitleaks container image: `containers/gitleaks/Dockerfile` (base) + `containers/gitleaks-tests/Dockerfile` (extends base + Python/pytest) + `docker-compose-files/gitleaks.yaml`.

## Tests (real gitleaks binary — no mocks on the detection path)
- [x] 3.1 `tests/test_secret_scanner.py` — 16 hermetic unit tests (mock only subprocess/paths).
- [x] 3.2 `tests/test_secret_scanner_integration.py` — 12 integration tests that write real example
       files at runtime and assert actual gitleaks rule output (slack-access-token detection, AWS
       example allowlist, empty input, clean source, staged blob, commit message, repo scan, CLI exit codes).
- [x] 3.3 Run `python -m pytest tests/test_secret_scanner.py tests/test_secret_scanner_integration.py` → **28 passed**.

## Hook wiring (fail-closed)
- [x] 4.1 `git-hooks/pre-commit` invokes `python3 scripts/secret_scanner.py --staged` (fail-closed) before the trailing-whitespace auto-fix.
- [x] 4.2 `git-hooks/commit-msg` invokes `python3 scripts/secret_scanner.py --message-file` (fail-closed) after the commitlint check.
- [x] 4.3 Hooks stay executable; they only run `python3` (no `git commit`) so they are inert during `make loop-*` (B4/B14).

## Makefile
- [x] 5.1 `make check-secrets` runs `scripts/secret_scanner.py --repo-scan` over the working tree (respects `.gitignore`; clean on the current repo).
- [x] 5.2 Added `secret-scan-image`, `secret-scan-tests-image`, `scan-staged`, `scan-commit`, `test-secret-scanner` targets.
- [x] 5.3 `install-git-hooks` copies both hooks (pre-existing); secret-scan step documented in the hook bodies.

## OpenSpec / docs sync (B8)
- [x] 6.1 Mirror the new secret-scan behaviour in `AGENTS.md`, `hermes/skills/openspec-loop-harness.md`, and `docs/openspec-engineering-loop-harness.md`.
- [x] 6.2 `openspec validate replace-trufflehog-with-gitleaks` passes.
- [x] 6.3 `make check-docs-sync` confirms B8 docs agree.
- [x] 6.4 (verification) `make check-secrets`, `make scan-staged`, and the pytest suite are all green.
