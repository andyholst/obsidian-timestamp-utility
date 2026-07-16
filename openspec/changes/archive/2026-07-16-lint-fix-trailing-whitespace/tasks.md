# Tasks — lint-fix-trailing-whitespace

- [x] 1.1 Author `git-hooks/pre-commit`: iterate staged files (`git diff --cached --name-only
  --diff-filter=ACM`), skip non-text/binary (probe with `file`/extension allowlist), strip
  trailing whitespace per line (`sed -i 's/[[:space:]]*$//'`), and `git add` the cleaned file back
  to the index. Auto-fix only — never exit non-zero on a clean diff.
- [x] 1.2 Extend `make install-git-hooks` to also `cp -f git-hooks/pre-commit .git/hooks/pre-commit
  && chmod +x` it (in addition to the existing `commit-msg` install), and `chmod +x` the source.
- [x] 2.1 Unit-check the hook logic in isolation: stage a file with trailing whitespace, run
  `bash git-hooks/pre-commit`, and assert the staged blob has no trailing whitespace
  (`git diff --cached` shows only whitespace removal, content otherwise identical).
- [x] 2.2 Assert the clean-file case makes no index change, and the binary/deleted case is skipped
  without error.
- [x] 3.1 Verify `make install-git-hooks` writes both `.git/hooks/commit-msg` and
  `.git/hooks/pre-commit` and both are executable.
- [x] 3.2 Confirm the hook does not break the loop: `make loop-collect` + `make loop-unit` stay
  green with the hook installed (loop performs no `git commit`, so the hook must be inert there).
- [x] 4.1 B8-sync: if AGENTS.md / openspec-loop-harness skill behaviour docs need a note that the
  pre-commit hook is loop-inert, add it; otherwise confirm no drift.
- [x] 5.1 `openspec validate lint-fix-trailing-whitespace` passes (this task ticks the moment the
  change is green).
