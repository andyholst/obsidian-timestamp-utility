# Proposal: Wire gitleaks secret scanning into the loop harness (containerized, no python)

## Why
The secret scanning we just added works, but it was wired as **standalone Makefile commands that
shell out to `python3 scripts/secret_scanner.py`** (`check-secrets`, `scan-staged`, `scan-commit`).
That violates two standing project rules:
1. **Execution is docker compose only (B9).** Every verification step in this repo runs inside a
   container via `docker-compose-files/*.yaml`. The Makefile must NOT invoke `python3` or a bare
   host binary for a gate — it must drive a compose service.
2. **Secret scanning is harness/loop-engineering, not a side command.** It belongs in the loop
   gate chain alongside `loop-build-app` / `loop-test-app`, so a leaked secret blocks the loop
   (fail-closed) exactly like a broken build/test would.

There is also **redundancy**: three different Makefile targets each independently ran gitleaks/Python.
That should collapse to exactly one canonical, containerized loop entry.

## What Changes
- **Rewrite `docker-compose-files/gitleaks.yaml`** so the `gitleaks` service runs
  `detect --source=/src --redact --config=/src/.gitleaks.toml` (honouring `.gitignore` and the
  repo `.gitleaks.toml` allowlists) — reusable as the loop stage.
- **Replace the Makefile secret-scan section**: remove `check-secrets` / `scan-staged` /
  `scan-commit` (python-backed); add `loop-secret-scan` that runs
  `docker compose -f docker-compose-files/gitleaks.yaml run --rm gitleaks`. Keep `secret-scan-image`
  (image build) and `test-secret-scanner` (pytest) as non-scan helpers.
- **Add `loop-secret-scan` to the loop stage chain** in `scripts/run-loop-harness.sh` (STAGES,
  stage_desc, timeout) and the Makefile `loop-harness` target — positioned after `loop-test-app`,
  before `check-docs-sync`.
- **B8 sync**: extend the canonical stage order in `AGENTS.md`, `hermes/skills/openspec-loop-harness.md`,
  and `docs/openspec-engineering-loop-harness.md` to include `loop-secret-scan`.
- **Hooks unchanged in spirit**: `git-hooks/pre-commit` and `git-hooks/commit-msg` keep the local
  fail-closed `scripts/secret_scanner.py` guard (developer-side, in-process Python is fine for a
  hook); only the **Makefile loop path** is containerized.

## Capabilities
- `loop-secret-scan` (new, part of the loop harness): gitleaks runs in a container as a mandatory
  gate; a leaked secret fails the loop. No python, no duplicate commands.

## Impact
- The loop-harness now enforces "no secrets in the working tree" with the same container discipline
  as every other gate (B9), with a single canonical `loop-secret-scan` target — no redundancy.
- `make check-docs-sync` stays green because the stage order is updated in all B8 sync docs.
- `tests/test_secret_scanner*.py` (the Python wrapper + real-gitleaks integration) remain the
  hook/developer guard and still pass (28 tests).
