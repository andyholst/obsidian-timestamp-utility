# Tasks: verify-bash-migration

## Contract
- All Makefile targets that previously called `.sh` scripts now call Python equivalents
- Each Python script produces identical output to its bash predecessor
- No `.sh` files remain in `scripts/` (except vendor artifacts: `install_dagger.sh`, `engine-wrapper.sh`)

## Test Contract
- `make openspec-new NAME=test` succeeds and validates
- `python3 scripts/run_loop_harness.py --hermetic` runs all stages successfully
- `python3 scripts/gen_changelog.py` generates changelog correctly
- No Makefile target invokes `.sh` files directly (grep returns 0 matches)

1.0 [ ] Verify `scaffold_openspec_change.py` works identically to `scaffold-openspec-change.sh`
    1.1 [ ] Run `python3 scripts/scaffold_openspec_change.py --name test-verify` and confirm it creates change dir
    1.2 [ ] Confirm `openspec validate test-verify` passes
    1.3 [ ] Clean up: remove the test change dir

2.0 [ ] Verify `gen_changelog.py` works identically to `gen_changelog.sh`
    2.1 [ ] Run `python3 scripts/gen_changelog.py` and confirm CHANGELOG.md is updated correctly
    2.2 [ ] Compare output format with expected structure (tag → conventional commits → merge)

3.0 [ ] Verify `run_loop_harness.py` works identically to `run-loop-harness.sh`
    3.1 [ ] Run `python3 scripts/run_loop_harness.py --hermetic` and confirm all stages execute
    3.2 [ ] Verify PASS/FAIL summary output matches expected format

4.0 [ ] Verify no Makefile target directly invokes `.sh` files
    4.1 [ ] Run `grep -E 'bash scripts/|\.sh' Makefile` and confirm 0 matches (excluding comments)
    4.2 [ ] Check all Makefile targets that previously called `.sh` now call Python

5.0 [ ] Remove original `.sh` files after verification
    5.1 [ ] Delete: `scripts/changelog.sh`, `scripts/scaffold-openspec-change.sh`, `scripts/gen_changelog.sh`
    5.2 [ ] Delete: `scripts/obsidian-tsu-opencode.sh`, `scripts/pr_resolve.sh`, `scripts/pr_comment.sh`
    5.3 [ ] Delete: `scripts/test_metrics.sh`, `scripts/release.sh`, `scripts/stop-containers.sh`
    5.4 [ ] Delete: `scripts/run-loop-harness.sh`, `scripts/openspec-change-flow.sh`, `scripts/ts_test_floor.sh`
    5.5 [ ] Keep: `scripts/install_dagger.sh`, `scripts/engine-wrapper.sh` (vendor artifacts)

6.0 [ ] Final validation
    6.1 [ ] `make openspec-new NAME=final-check CAPABILITY=test` succeeds and validates
    6.2 [ ] `python3 scripts/run_loop_harness.py --hermetic` runs successfully
    6.3 [ ] `grep -E 'bash scripts/|\.sh' Makefile` returns 0 matches (excluding comments)
