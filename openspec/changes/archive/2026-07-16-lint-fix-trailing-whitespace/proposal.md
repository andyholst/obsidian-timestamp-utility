# Proposal: lint-fix-trailing-whitespace

## Why
Trailing whitespace (spaces/tabs at end of a line) is a recurring source of noisy diffs and
lint failures in this repo. It currently slips into commits because nothing strips it at commit
time. The existing `git-hooks/commit-msg` hook lints *commit messages* (Conventional Commits),
but nothing touches *file content*. We need an automatic, fail-soft guard that keeps committed
code clean without requiring humans to remember a cleanup step.

## What Changes
- Add a new hook `git-hooks/pre-commit` that, on every `git commit`, walks the **staged** files
  and strips trailing whitespace from text files, re-staging the cleaned content so the committed
  blob has no trailing whitespace. It auto-fixes the index (does NOT reject the commit).
- Extend `make install-git-hooks` (currently copies only `commit-msg`) so it also installs the new
  `git-hooks/pre-commit` into `.git/hooks/pre-commit` and marks it executable.
- The hook is text-file aware: it skips binary/deleted/untracked files and never blocks a valid
  commit. It performs no git commit/push of its own (B4/B14).

## Capabilities
- `lint-trailing-whitespace` (new): a pre-commit hook that automatically removes trailing
  whitespace from staged text files before the commit is written.

## Impact
- **MUST NOT regress:** the agentic loop (`make loop-harness` and its 8 stages), the deterministic
  TS-merge floor (B11), and the no-commit/no-push rule (B4/B14). Note the loop never runs
  `git commit` (B4), so the pre-commit hook does NOT execute during loop verification — it only
  affects real, human-initiated commits. The hook must therefore be safe to install on a machine
  that also runs the loop.
- **Side effects:** developers who have not run `make install-git-hooks` are unaffected; the hook
  only activates after install. Re-staging cleaned files may re-touch the index, so the hook must
  preserve already-staged intent (only whitespace changes, nothing else).
- **Dependencies:** bash + `git` + `file` (already present on the host). No new npm dependency.
