# pr-agent-comment-resolve Specification

## Purpose
TBD - created by archiving change pr-agent-comment-resolve. Update Purpose after archive.
## Requirements
### Requirement: Agent comments its fixes on the PR
When the agent applies a code fix in response to a PR comment or review thread, the system MUST post a
PR comment describing the fix and linking the fixing commit, so the participant can resolve the thread.

#### Scenario: post a fix comment after addressing a review comment
- **WHEN** the agent completes a code fix for a specific PR comment or review thread
- **THEN** it posts a PR comment (via `gh pr comment`) referencing the original comment/thread and the
  fixing commit sha (e.g. `Fixed in <sha>: <summary> — resolves <comment>`), and leaves the thread for
  the human participant to resolve/approve (the agent does NOT self-resolve or approve)

#### Scenario: pr-comment refuses without a PR or token
- **WHEN** `scripts/pr_comment.sh <branch> <body>` runs but `<branch>` has no open PR or `GH_TOKEN` is unset
- **THEN** it reports the problem and exits non-zero without posting

### Requirement: Agent commits on green loop gate (no squash)
When resolving an open PR's comments, the system MUST run `make loop-harness` and, when it is GREEN,
commit the fix(es) as normal (non-squashed) Conventional commits and push the PR branch normally.

#### Scenario: commit and push normally after green gate
- **WHEN** the agent has applied fixes for the PR's comments and `make loop-harness` (B20 pre-flight) is GREEN
- **THEN** the agent commits the fixes as NORMAL (non-squashed) Conventional commits, posts the fix
  comments (B29a), and pushes the PR branch normally (no `--force`, no squash)

#### Scenario: do not push on a red gate
- **WHEN** `make loop-harness` is RED (any stage failed)
- **THEN** the agent does NOT commit/push the fixes; it reports the failing stage and stops (B20)

