# Change: migrate-bash-to-python

## Why

The repo currently relies on shell scripts (`*.sh`) for core workflow commands: changelog generation, release prep, loop-harness execution, openspec scaffolding/flow, and the ts-test-floor guard. Shell scripts are a poor fit here because:

- They introduce a second scripting language alongside the Python agentic pipeline, increasing maintenance burden.
- Bash-specific features (arrays, process substitution, version quirks) cause portability headaches across macOS/system bash vs brew bash and Docker alpine images.
- Errors in shell are noisy and harder to diagnose than traced Python exceptions.
- The existing Makefile + Python tooling already handle environment setup; duplicating that logic in bash is wasteful.

Migrating all `.sh` scripts to Python consolidates execution on a single, well-tested language and makes workflows easier to extend, debug, and test.

## What Changes

- Replace the following bash scripts with Python equivalents under `scripts/`:
  - `scaffold-openspec-change.sh` → `scaffold_openspec_change.py`
  - `changelog.sh` → (merged into existing `gen_changelog.py` / updated to be canonical)
  - `gen_changelog.sh` → `gen_changelog.py`
  - `release.sh` → `release.py`
  - `run-loop-harness.sh` → `run_loop_harness.py`
  - `openspec-change-flow.sh` → `openspec_change_flow.py`
  - `ts_test_floor.sh` → merged into Makefile target (simple check, no standalone needed)
- Update `Makefile` targets to invoke Python scripts instead of `.sh`.
- Remove all original `.sh` scripts after verification.

Capabilities:

- Capability: python-workflow-scripts — all core workflows run via Python, called from Makefile / CLI.

## Capabilities

- See `specs/migration/spec.md`.

## Impact

- Breaking: any CI/workflows or local docs that directly invoke the old `.sh` paths must update (will be updated as part of this change).
- Non-breaking: Makefile consumers are preserved; only internal dispatch changes from bash to Python.
