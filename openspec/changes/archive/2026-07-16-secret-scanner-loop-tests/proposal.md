# Proposal: run the secret-scanner test suite as a loop-harness stage

## Why
The loop-harness runs `loop-secret-scan` (a gitleaks scan of the repo) but never
exercises the secret-scanner's own pytest suite — `tests/test_secret_scanner.py`
(wrapper/hook guard) and `tests/test_secret_scanner_integration.py` (real gitleaks,
no mocks). A regression in `scripts/secret_scanner.py` or `.gitleaks.toml` could pass
the repo scan yet ship broken detection. The scanner must verify ITSELF on every loop.

## What Changes
- Add `loop-secret-scan-tests` loop stage: builds `secret-scan-tests-image` (from
  `containers/gitleaks-tests/Dockerfile`, which layers pytest + the real gitleaks
  binary onto the base image) and runs `tests/test_secret_scanner*.py` inside the
  `gitleaks-tests` container — docker compose only (B9), hermetic, fail-closed.
- `test-secret-scanner` remains a host-side convenience helper (not a loop entry).
- Wire the stage into `scripts/run-loop-harness.sh` (STAGES/timeout/desc) directly
  after `loop-secret-scan`, and update the B8 canonical chain in AGENTS.md / skill /
  docs so the stage order stays in sync (no drift -> `check-docs-sync` stays green).

## Capabilities
- `loop-secret-scan` (extends the secret-scanning discipline)

## Impact
- Only the loop wiring, the `gitleaks-tests` image usage, and B8 docs change.
- No generated TS / agentic behaviour affected. Nothing committed/pushed (B4/B14).
