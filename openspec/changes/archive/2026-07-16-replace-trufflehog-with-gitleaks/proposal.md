# Proposal: Replace TruffleHog GitHub Action with gitleaks (pre-commit + commit-msg secret validator)

## Why
The CI "TruffleHog Secret Scan" workflow (`.github/workflows/trufflehog.yml`) is
**broken** and blocks every push/PR. The run at
`https://github.com/andyholst/obsidian-timestamp-utility/actions/runs/29472492781/job/87538291679`
failed with two distinct defects:

1. **Invalid action inputs** — the workflow passes `verified_only` and `ignore_paths`,
   neither of which is accepted by `trufflesecurity/trufflehog@main`. The action
   rejects them with:
   `Unexpected input(s) 'verified_only', 'ignore_paths', valid inputs are ['path', 'base', 'head', 'extra_args', 'version', 'image']`.
2. **BASE == HEAD** — when the base/head computation resolves to the same commit
   (e.g. a direct push to a branch), TruffleHog aborts:
   `BASE and HEAD commits are the same. TruffleHog won't scan anything.` and exits 1.

TruffleHog's GitHub Action has been a chronic source of fragility (tracked
upstream as unstable action inputs). The user asked to **replace it with a solid,
genuinely good open-source plugin** that validates commit messages / staged content
for secrets and **does not let secrets into the commit**.

The right tool is **gitleaks** — the de-facto open-source secret scanner
(Apache-2.0, ~18k stars, actively maintained, used by major orgs). It is far more
stable than the TruffleHog *Action wrapper*, and crucially it is designed to run as
a **git pre-commit / commit-msg hook** so secrets are caught **locally, before
they ever reach a remote** — exactly the "validate our commit message pre-commit so
it does not include any secrets" requirement.

This change:
- **Replaces** the broken TruffleHog Action in `.github/workflows/trufflehog.yml` with a
  gitleaks-based workflow (`gitleaks/gitleaks-action@v2`, `fetch-depth: 0`,
  `GITLEAKS_CONFIG=.gitleaks.toml`) — keeping the same file name so no other wiring changes.
- Adds a gitleaks-based **local** secret validator wired into `git-hooks/pre-commit`
  and `git-hooks/commit-msg`, installed by the existing `make install-git-hooks`.
- Adds a **Python engine** (`scripts/secret_scanner.py`) that **delegates 100% of detection to
  gitleaks** (no homemade regex/entropy detector): it prefers running gitleaks inside a container
  image (nerdctl/docker) and falls back to a local `gitleaks` binary (`GITLEAKS_BIN`);
  `GITLEAKS_RUNTIME=none|false|0` forces binary mode. It exposes a clean, testable API used by
  both hooks and the tests.
- Writes **thorough Python tests** — `tests/test_secret_scanner.py` (16 hermetic unit tests) and
  `tests/test_secret_scanner_integration.py` (12 integration tests that write real example files
  and assert actual gitleaks rule output, no mocks on the detection path).

## What Changes
- **Replace** `.github/workflows/trufflehog.yml` with a gitleaks GitHub Action that scans every
  push/PR correctly (`gitleaks/gitleaks-action@v2`, `fetch-depth: 0`, config `.gitleaks.toml`), so
  the repo still has a *server-side* backstop while the primary guard is the fast local
  pre-commit/commit-msg hook.
- **Add** `.gitleaks.toml` — explicit gitleaks config (extends the default ruleset via
  `useDefault = true`, with repo-appropriate `allowlist` for test fixtures / docs / dependency and
  build caches / `.env`).
- **Add** `containers/gitleaks/Dockerfile` (base gitleaks image), `containers/gitleaks-tests/Dockerfile`
  (extends base + Python/pytest), and `docker-compose-files/gitleaks.yaml`.
- **Add** `scripts/secret_scanner.py` — the Python engine (gitleaks-only):
  - `scan_staged_content()` — reads the staged (index) content via `git show :<file>` and scans it.
  - `scan_commit_message(text)` — scans a commit-message string.
  - `scan_file(path)` / `scan_text(text)` — scan a file / inline string.
  - `scan_repo()` — recursive scan of the working tree (honours `.gitignore`).
  - Returns a structured `ScanResult` (clean bool, list of findings, engine).
- **Wire** the engine into `git-hooks/pre-commit` (scan staged content) and
  `git-hooks/commit-msg` (scan the message file), so a `git commit` that would
  introduce a secret is **rejected** (fail-closed), while a clean commit passes.
- **Enhance** `make check-secrets` to run `scripts/secret_scanner.py --repo-scan` (clean on the
  current repo), and add `secret-scan-image`, `secret-scan-tests-image`, `scan-staged`,
  `scan-commit`, and `test-secret-scanner` targets.
- **Add** `tests/test_secret_scanner.py` (hermetic) and `tests/test_secret_scanner_integration.py`
  (real gitleaks binary, no mocks on detection).

## Capabilities
- `secret-scan` (new): a gitleaks-backed secret scanner is wired as a pre-commit and
  commit-msg guard, with a hermetic Python engine + tests, replacing the broken
  TruffleHog Action.

## Impact
- CI red on every push (the TruffleHog failure) is eliminated; gitleaks provides a
  stable server-side scan.
- Developers get an immediate **local** guardrail: a secret is blocked at the
  `git commit` step, never reaching history or the remote.
- No change to the agentic loop (the hook is inert during `make loop-*` because no
  `git commit` occurs there — consistent with the existing trailing-whitespace hook's
  design, B4/B14).
- The scanning logic is testable in isolation; adding new secret patterns later is a
  config/rule change, not a code rewrite.
