# Tasks: migrate-bash-to-python

## Contract
- Python scripts MUST use `/usr/bin/env python3` shebang.
- Python scripts MUST be importable (use `if __name__ == "__main__"` guard).
- No Makefile target may invoke `.sh` files directly; all must route through `python3 scripts/...`.

## Test Contract
- Each target (`make openspec-new`, `make changelog`, `python3 scripts/run_loop_harness.py`) MUST pass when exercised.

1.0 [x] Read and analyze each bash script to document its exact behavior (inputs, outputs, exit codes)
    1.1 [x] Analyze scaffold-openspec-change.sh (NAME/CAPABILITY inputs, openspec CLI call, seed files, validate)
    1.2 [x] Analyze gen_changelog.sh (git log since last tag, conventional-commit mapping, merge into CHANGELOG.md)
    1.3 [x] Analyze changelog.sh (full changelog from tags, release_notes extraction)
    1.4 [x] Analyze release.sh (artifact set in ./release/, version from package.json or TAG env, DRY_RUN support, repo-root resolution)
    1.5 [x] Analyze run-loop-harness.sh (ordered stages, live output via script/setsid PTY synth, per-stage summary)
    1.6 [x] Analyze openspec-change-flow.sh (worktree creation wt/<name>, confined lifecycle: flow → run-agentics → loop → archive → finalize; --push promotion + PR)
    1.7 [x] Analyze ts_test_floor.sh (describe/it/test/addCommand counts comparison vs origin/main)
    1.8 [x] Analyze pr_resolve.sh (B28b: gh PR view, comments/reviews fetch for branch)
    1.9 [x] Analyze pr_comment.sh (B29a: gh pr comment to an open PR for a branch)

2.0 [x] Implement Python equivalents for each script
    2.1 [x] Write scripts/scaffold_openspec_change.py (wraps openspec new change, seeds proposal/tasks/spec, runs validate)
    2.2 [x] Write scripts/gen_changelog.py (replicate gen_changelog.sh range-based changelog generation and merge)
    2.3 [x] Write scripts/changelog_closed.py or update gen_changelog.py (full tag-based changelog generation)
    2.4 [x] Write scripts/release.py (artifact prep: version read, build trigger, release_notes extraction to ./release/)
    2.5 [x] Write scripts/run_loop_harness.py (ordered stages execution with setsid PTY for nerdctl output, PASS/FAIL summary)
    2.6 [x] Write scripts/openspec_change_flow.py (worktree-constrained lifecycle: create wt/<name> → scaffold inside → generate → loop → archive → finalize; --push promotion + PR delivery)
    2.7 [x] Either write scripts/ts_test_floor.py or inline logic into Makefile's loop-ts-floor target

3.0 [x] Update Makefile targets to call Python instead of bash
    3.1 [x] Update openspec-new target → python3 scripts/scaffold_openspec_change.py
    3.2 [x] Update changelog / gen-changelog targets → python3 scripts/gen_changelog.py
    3.3 [x] Update release / build-release targets → python3 scripts/release.py
    3.4 [x] Update run-loop-harness invocation docs in Makefile to reference python3 scripts/run_loop_harness.py
    3.5 [x] Update loop-ts-floor target → python3 or inline

4.0 [x] Verify each migrated script works identically to its bash predecessor
    4.1 [x] Run make openspec-new NAME=verify-bash-migration CAPABILITY=test and confirm validate passes
    4.2 [x] Run make changelog from a repo with tags and compare output format to expected structure
    4.3 [x] Run python3 scripts/run_loop_harness.py and confirm all stages execute in order with real output
    4.4 [x] Run ts-test-floor equivalent (python3 scripts/ts_test_floor.py) and confirm it correctly detects if test/command counts dropped below origin/main

5.0 [x] Remove original .sh files after verification (keep install_dagger.sh / engine-wrapper.sh as vendor artifacts if applicable)
    5.1 [x] scaffold-openspec-change.sh removed (Python version exists)
    5.2 [x] gen_changelog.sh removed (Python version exists)
    5.3 [x] run-loop-harness.sh removed (Python version exists)
    5.4 [x] openspec-change-flow.sh removed (Python version exists)
    5.5 [x] release.sh removed (Python version exists)
    5.6 [x] ts_test_floor.sh removed (Python version exists)

6.0 [x] Verify no Makefile target directly invokes a .sh file under scripts/ (grep 'bash scripts/' Makefile must return 0 matches)