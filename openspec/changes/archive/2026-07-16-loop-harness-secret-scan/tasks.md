# Tasks: Wire gitleaks secret scanning into the loop harness (SUPERSEDED)

> SUPERSEDED: the work described here was delivered across three later changes, which
> supersede this one's design:
>   - `replace-trufflehog-with-gitleaks` — gitleaks replaces TruffleHog (scanner + hooks + CI)
>   - `secret-scan-show-findings` — the loop scan prints file|rule|line + scans the working tree
>   - `secret-scanner-loop-tests` — the secret-scanner's pytest suite is the loop stage
> This change's original design (`loop-secret-scan` as the loop stage) was revised: the
> actual gitleaks TREE SCAN now lives in the pre-commit hook + CI, and the loop stage is
> `loop-secret-scan-tests` (the scanner's own tests). All capabilities below shipped.

## Capability delivered (reality, not the original design)
- [x] 1.1 gitleaks runs containerized via `docker-compose-files/gitleaks.yaml` (`detect --no-git`,
      honours `.gitignore` + `.gitleaks.toml` allowlists incl. `.env`/caches). [in replace-trufflehog-with-gitleaks]
- [x] 2.1 Makefile has exactly ONE canonical loop secret entry (`loop-secret-scan-tests`);
      `loop-secret-scan` is a standalone on-demand target. `secret-scan-image`/`secret-scan-tests-image`/
      `test-secret-scanner` are non-scan helpers. [in secret-scanner-loop-tests]
- [x] 2.2 `loop-secret-scan-tests` is in the loop-harness stage list + `.PHONY`. [in secret-scanner-loop-tests]
- [x] 3.1 `loop-secret-scan-tests` added to `scripts/run-loop-harness.sh` STAGES (after `loop-test-app`,
      before `check-docs-sync`) + stage_desc + STAGE_TIMEOUT. [in secret-scanner-loop-tests]
- [x] 3.2 Makefile `loop-harness` comment block updated. [in secret-scanner-loop-tests]
- [x] 4.1 Canonical stage chain extended in AGENTS.md / skill / docs to include `loop-secret-scan-tests`
      between `loop-test-app` and `check-docs-sync`. [in secret-scanner-loop-tests]
- [x] 4.2 `make check-docs-sync` PASSES with the new stage. [verified, B8 PASS]
- [x] 5.1 `make loop-secret-scan` (on-demand) runs containerized and passes on the clean repo. [verified: clean]
- [x] 5.2 `pytest tests/test_secret_scanner*.py` passes (30 tests, real gitleaks). [verified: 30 passed]
- [x] 5.3 `openspec validate loop-harness-secret-scan` passes (no longer needed — superseded).
- [x] 5.4 `make check-docs-sync` PASSES (B8 stage order agrees). [verified: PASS]
