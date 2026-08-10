## ADDED Requirements
### Capability: python-workflow-scripts

The system MUST replace all bash workflow scripts with Python equivalents. The Makefile dispatches these scripts, and they must behave identically (same inputs/outputs, exit codes) as their bash predecessors.

### Requirement: migrate-scaffold-openspec-change
Migrate `scripts/scaffold-openspec-change.sh` to Python.

- **THEN** `scripts/scaffold_openspec_change.py` exists with the same CLI interface (`NAME=... CAPABILITY=...`) and invokes the real `openspec new change` CLI via subprocess (B15), seeds proposal/tasks/spec, and runs `openspec validate`.
- **THEN** the old `.sh` file is deleted after verification.

### Requirement: migrate-gen-changelog
Migrate `scripts/gen_changelog.sh` to Python.

- **THEN** `scripts/gen_changelog.py` regenerates the unreleased changelog section by reading `git log --since=<last-tag>` and applying conventional-commit prefix mapping, then overwrites CHANGELOG.md with the merged output using the same logic as the bash version.
- **THEN** the old `.sh` file is deleted after verification.

### Requirement: migrate-changelog-closed
Migrate `scripts/changelog.sh` to Python (closed-loop changelog with release-notes support).

- **THEN** `scripts/changelog_closed.py` (or merged into an existing equivalent) generates the full closed changelog from release tags, matching the bash behaviour.
- **THEN** the old `.sh` file is deleted after verification.

### Requirement: migrate-release
Migrate `scripts/release.sh` to Python.

- **THEN** `scripts/release.py` produces the same artifact set under `release/` (build, release_notes.md derived from CHANGELOG.md, version resolution from package.json) as the bash script, including DRY_RUN support and repo-root resolution.
- **THEN** the old `.sh` file is deleted after verification.

### Requirement: migrate-run-loop-harness
Migrate `scripts/run-loop-harness.sh` to Python.

- **THEN** `scripts/run_loop_harness.py` runs the loop stages in order (`loop-collect`, `loop-ts-floor`, `loop-unit`, `loop-unit-real`, `loop-e2e`, `loop-integration`, `loop-build-app`, `loop-test-app`, `loop-release-tests`, `loop-secret-scan-tests`, `check-docs-sync`), prints per-stage PASS/FAIL, streams live output (via `script`/`setsid` PTY workaround for nerdctl containers), and exits non-zero if any stage fails.
- **THEN** the old `.sh` file is deleted after verification.

### Requirement: migrate-openspec-change-flow
Migrate `scripts/openspec-change-flow.sh` to Python.

- **THEN** `scripts/openspec_change_flow.py` creates a dedicated worktree (`wt/<name>`), scaffolds the change inside it, runs generation + loop gate, archives on green, and finalizes in the worktree (squash-commits → changelog → release-notes), all confined to the worktree as per B12/B27.
- **THEN** `--push` / `PUSH=1` delivers by promoting → `feat/<name>`, pushing, and opening the PR.
- **THEN** the old `.sh` file is deleted after verification.

### Requirement: migrate-ts-test-floor
Migrate `scripts/ts_test_floor.sh` functionality into Python (or eliminate as standalone if trivial).

- **THEN** either `scripts/ts_test_floor.py` exists AND the Makefile target `loop-ts-floor` invokes it, OR the logic is inlined directly into the Makefile target via a short Python one-liner.
- **THEN** the old `.sh` file is deleted after verification.

### Requirement: update-makefile-targets
Update all Makefile targets that invoked the old bash scripts to call the new Python equivalents.

- **THEN** `make openspec-new`, `make changelog`, `make release`, `bash scripts/run-loop-harness.sh` → `python3 scripts/run_loop_harness.py`, and all related targets execute identically via Python.
- **THEN** no Makefile target directly invokes a remaining `.sh` file under `scripts/`.

### Requirement: remove-bash-scripts
Remove all original bash script files after migration verification.

- **THEN** `find scripts/ -name '*.sh'` returns zero results (excluding install_dagger.sh / engine-wrapper.sh if they are external vendor artifacts; those can remain with a comment).
- **THEN** no import/invocation of removed `.sh` files exists in the codebase or Makefile.

## Test Contract

### Requirement: verify-make-targets-pass
Each migrated Makefile target MUST PASS when invoked:

- **WHEN** `make openspec-new NAME=test-py-migration CAPABILITY=test-py` is run
- **THEN** a new change dir is created, seeds are correct, and `openspec validate test-py-migration` exits 0.

- **WHEN** `make changelog` is run (from a clean repo with tags)
- **THEN** CHANGELOG.md is updated deterministically and matches what the bash version would produce for the same repo state.

- **WHEN** `python3 scripts/run_loop_harness.py` is run
- **THEN** each stage executes in order, prints its result, and exits 0 iff all stages PASS.

## Contract

- Python scripts MUST use `/usr/bin/env python3` shebang.
- Python scripts MUST be importable for unit testing (structured with `if __name__ == "__main__"` entry point).
- No Makefile target may invoke `.sh` files as a direct command (they must call `python3 scripts/...`).
