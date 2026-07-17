## ADDED Requirements

### Requirement: Agent works in a local worktree sandbox during the change
The agent MUST implement every OpenSpec change inside an isolated **local** git worktree sandbox
(`worktrees/<name>` on a throwaway branch `wt/<name>`) by default. The parent working tree MUST
NOT be modified while the change is in progress.

#### Scenario: change worked in isolation
- **WHEN** the agent opens/implements an OpenSpec change
- **THEN** it works only inside `worktrees/<name>` on branch `wt/<name>`, runs the loop gate there,
  archives there, and the parent working tree is untouched

#### Scenario: multiple agents run in parallel
- **WHEN** several agents each work different changes concurrently
- **THEN** each uses its own `wt/<name>` sandbox with a unique `COMPOSE_PROJECT_NAME=otu-<name>`,
  and no two ever share a branch or compose project name

### Requirement: On completion the agent AUTO-delivers the PR (no second prompt)
As soon as the change is COMPLETE — every `tasks.md` checkbox ticked, the loop gate green, and the
pre-commit hook passing — the agent MUST automatically promote `wt/<name>` to `feat/<name>`, push
it, and open the PR. Green-lighting a change IS the delivery authorization; no further "make the
PR" prompt is required. The `--no-push` flag opts out and keeps the work in the local sandbox.

#### Scenario: change completes green
- **WHEN** all tasks are ticked and the loop gate + pre-commit hook are green
- **THEN** the agent promotes `wt/<name>` to `feat/<name>`, pushes `origin feat/<name>`
  (parallel-safe: unique branch + `otu-<name>`), and opens the PR; the parent working tree stays untouched

#### Scenario: gate or hook not green
- **WHEN** the loop gate is red or the pre-commit hook fails
- **THEN** the agent does NOT create/push the branch and reports the failing gate instead

### Requirement: Push uses token auth from .env when SSH is unavailable
The delivery push MUST resolve an authenticated URL. When the SSH transport is unavailable (no
host-key/askpass in the sandbox), the flow MUST read `GH_TOKEN` from the repo-root `.env`
(gitignored) and push via `https://x-access-token:<token>@host/repo`. This lets the auto-delivery
complete without manual SSH setup. The `.env` file MUST stay gitignored and its contents MUST NOT
be printed or committed.

#### Scenario: SSH transport unavailable
- **WHEN** `git push` would fail due to missing SSH host-key / askpass
- **THEN** the flow reads `GH_TOKEN` from `.env`, rewrites the push URL to token-authenticated
  HTTPS, and pushes successfully (no credential is echoed)

### Requirement: Docs must state one consistent rule
AGENTS.md, the loop-harness skill, the harness doc, the Makefile, and `openspec-change-flow.sh`
MUST agree on: default = local `wt/<name>` sandbox; auto-promote to `feat/<name>` + open PR on
completion; parallel-safe delivery; token-from-`.env` push fallback. No file may imply a
contradictory model.

#### Scenario: Phase 5 consistency
- **WHEN** a reader inspects Phase 5 of AGENTS.md
- **THEN** it shows `wt/<name>` as the standing sandbox and states that completion auto-promotes to
  `feat/<name>` and opens the PR

#### Scenario: flow script default
- **WHEN** `make openspec-flow NAME=<x>` runs
- **THEN** it creates the `wt/<name>` sandbox, runs the loop gate, archives, finalizes, and
  auto-promotes to `feat/<name>` + opens the PR on completion (unless `--no-push`)
