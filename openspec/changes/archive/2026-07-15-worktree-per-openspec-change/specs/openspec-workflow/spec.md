## ADDED Requirements

### Requirement: Per-change isolated worktree
The system MUST implement each OpenSpec change in a dedicated linked git worktree keyed by the
change name (`../worktrees/<name>`, branch `wt/<name>`), never on the parent branch directly.

#### Scenario: Agent creates and implements a change
- **WHEN** the agent runs `make openspec-new NAME=<name>` and begins implementation
- **THEN** it spawns `git worktree add ../worktrees/<name> -b wt/<name>` and performs ALL
  implementation, agentic generation, and verification inside that worktree, leaving the parent
  branch's committed history and uncommitted work untouched.

### Requirement: Forbid destructive operations on the parent branch
The agent MUST NOT run `git reset --hard`, `git reset --mixed` past authored commits,
`git checkout --` on source files, `git branch -D` on a branch holding un-synced fix-work, or
`git clean -fd` on the parent branch.

#### Scenario: A risky/reset-capable operation is needed
- **WHEN** the agent needs to discard/reset/rewind work during implementation or test cleanup
- **THEN** it performs that operation INSIDE the change's worktree (or a throwaway `wt/<name>`
  branch), never on the parent, so the parent's history cannot be destroyed.

### Requirement: Sync back to parent only when green
The agent MUST sync a change's worktree back to the parent branch ONLY after the change's
`tasks.md` is fully ticked AND `openspec validate <name>` is clean AND the loop gate is green.

#### Scenario: Change completes successfully
- **WHEN** all tasks are ticked and verification passes in the worktree
- **THEN** the agent merges `wt/<name>` into the parent (or cherry-picks the squashed result),
  runs `git worktree remove ../worktrees/<name>` and deletes `wt/<name>`, leaving a single clean
  merge on the parent.

#### Scenario: Change is abandoned or broken
- **WHEN** a change cannot be completed or is superseded
- **THEN** the agent deletes its worktree + `wt/<name>` branch WITHOUT touching the parent, so no
  partial/broken work lands on the parent branch.

### Requirement: Compose-mount fallback inside worktree
When a worktree's docker-compose `make` targets fail due to repo-root resolution (relative `..`
mount, see B19), the agent MUST validate the pipeline logic by running the underlying scripts
directly in the worktree, and reserve compose `make` targets for the parent/CI.

#### Scenario: make container target fails in worktree
- **WHEN** `make <container-target>` errors on mount-root resolution inside `../worktrees/<name>`
- **THEN** the agent runs the target's script directly (e.g. `bash scripts/gen_changelog.sh`,
  `python3 scripts/bump_from_changelog.py`) to prove the logic, and syncs back via the parent for
  the full compose run.
