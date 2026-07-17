# pr-fix-no-revert Specification

## ADDED Requirements

### Requirement: Reverting commits is never allowed
The system MUST NOT run `git revert` on any branch. Corrections are always made by adding a new
forward NORMAL commit; history is never undone via revert.

#### Scenario: a defect is found after a commit
- **WHEN** a bug or regression is found in already-committed work (on any branch, including a PR branch)
- **THEN** the agent fixes it by adding a NEW forward NORMAL (non-squashed) commit — it MUST NOT run
  `git revert`, `git reset`, `git rebase -i` (squash/fixup), or any history-rewriting command

#### Scenario: loop gate red after a push
- **WHEN** `make loop-harness` is RED after the branch was already pushed / is an open PR
- **THEN** the agent adds a forward fixup commit (and a PR comment per B29a if resolving a review
  thread) — it NEVER reverts/rewrites the pushed history to "undo" the work

### Requirement: Squash only occurs before a branch becomes a PR
The system MUST permit squash ONLY while the branch is a local change that has not yet become an open PR.
Once pushed / an open PR exists, squash is forbidden.

#### Scenario: squash attempted on a pushed / open-PR branch
- **WHEN** `make squash-commits` / `make loop-finish` / `make openspec-redeliver` runs on a branch that
  `gh pr view` reports as an open PR (or that already tracks a pushed remote state)
- **THEN** the target refuses (fail closed) and performs NO commit/reset/push — squash is pre-PR only

#### Scenario: squash allowed on a clean local pre-PR branch
- **WHEN** the branch is local, not yet an open PR, and `gh` confirms no PR exists for it
- **THEN** squash is permitted (the pre-PR finalization path)
