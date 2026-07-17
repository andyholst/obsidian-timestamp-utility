# pr-review-stability Specification

## Purpose
TBD - created by archiving change pr-review-no-squash. Update Purpose after archive.
## Requirements
### Requirement: No squash after a PR has reviewer engagement
The system MUST NOT squash or force-rewrite the history of a branch that is the head of a
pull request with reviewer engagement. "Reviewer engagement" means the PR reports at least
one comment, at least one review, or at least one non-dismissed review thread.

#### Scenario: squash attempted on an engaged PR
- **WHEN** `make squash-commits`, `make loop-finish`, or `make openspec-redeliver` runs on a
  branch that `gh pr view` identifies as an open PR with `comments > 0` OR `reviews > 0` OR a
  non-dismissed review thread
- **THEN** the target fails closed with a clear message naming the PR number and stating
  squash is forbidden by B28, and it makes NO commit, NO reset, and NO push

#### Scenario: corrections after engagement land as normal commits
- **WHEN** a fix is needed on a PR branch that already has reviewer engagement
- **THEN** the fix is committed as a normal (non-squashed) Conventional commit on that branch
  and pushed normally (no `--force`, no squash), preserving the incremental reviewable diff

#### Scenario: gh unavailable does not block local squash
- **WHEN** `gh` or the GitHub token is unavailable so engagement cannot be confirmed
- **THEN** the guard is skipped and the squash proceeds (fail-open on network, fail-closed on
  confirmed engagement)

### Requirement: gh-driven PR comment resolution mode
When instructed to "go to the PR for `<branch>`" (or equivalently "address the PR comments"
/ "resolve the review"), the system MUST fetch the PR's comments and review threads via the
`gh` CLI and resolve them as incremental commits.

#### Scenario: resolve PR comments on request
- **WHEN** the human/agent prompt asks to go to the PR for `<branch>` and resolve its comments
- **THEN** the system runs `make pr-resolve BRANCH=<branch>` (or `scripts/pr_resolve.sh`),
  which uses `gh` to list the PR's comments + review threads, and the agent follows each
  strictly, commits the fixes as normal Conventional commits, and pushes the PR branch normally
  (never `--force`, never squash)

#### Scenario: pr-resolve refuses on a branch with no open PR
- **WHEN** `make pr-resolve BRANCH=<branch>` is run but `<branch>` is not the head of an open PR
- **THEN** it reports that no open PR was found for the branch and exits without committing or
  pushing

