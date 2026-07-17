# Proposal: Agent must NOT create named/remote branches or PRs without explicit human say-so (B27)

## Why
The user flagged a real governance gap: the agent must **never** create a named feature branch
(`feat/<name>`) or push to a remote branch / open a PR **unless the human explicitly says so**.
Inside a change, the agent's default MUST be a **local worktree sandbox** that is self-contained
(the parent working tree is never touched, no remote branch is created). Only when the human says
"make the PR", "push it", or "create the remote branch" does the agent promote that sandbox to a
`feat/<name>` branch and deliver it. This promotion MUST be safe to run **in parallel** — multiple
agents each iterating in their own sandbox, then each delivering their own PR branch concurrently.

Today the docs are split and partly contradict this:
- `wt-create` / `openspec-flow` / `openspec-change-flow.sh` **always** create a `feat/<name>` branch
  immediately and (with `PUSH=1`) push it + open a PR on their own.
- B12 states delivery = "push `feat/<name>` as the PR" as the default agent action.
- B26 lets the agent push its own branch after the gate is green.
- Phase 5 (AGENTS.md) is internally inconsistent: it shows `git worktree add ... -b feat/<name>`
  (line ~133) but the standing rule (line ~143) says `-b wt/<name>` (a throwaway sandbox).

None of these state the single clear rule the user wants: **worktree sandbox is the default; a
named remote PR branch is created ONLY on explicit human instruction; and multiple such sandboxes
deliver concurrently to distinct PR branches.**

## What Changes
- Add durable behaviour **B27**: "Agent must prompt / wait for explicit human say-so before creating
  a named `feat/<name>` branch, pushing to a remote, or opening a PR. Default mode = local `wt/<name>`
  worktree sandbox (no remote branch). Promotion to `feat/<name>` + push happens ONLY when the human
  explicitly requests delivery; that promotion is parallel-safe (unique branch + unique compose
  project name per change)."
- Reconcile the contradictions:
  - Phase 5: make the standing rule `wt/<name>` (local sandbox) the single instruction; the
    `feat/<name>` form becomes the *explicit-delivery* promotion only.
  - B12: clarify the "deliver as PR" step is the **explicit** human-triggered promotion, not an
    automatic agent action; the default flow ends at a green local sandbox.
  - `openspec-flow` / `wt-create` / `openspec-change-flow.sh`: default to a local `wt/<name>`
    sandbox; a named `feat/<name>` remote branch + PR is created **only when PUSH=1 is explicitly
    passed by the human** (which is exactly the "go make the PR" instruction). Add the parallel-safe
    contract (unique branch name + `COMPOSE_PROJECT_NAME=otu-<name>`).

## Capabilities
- `agent-branch-governance` — controls when the agent may create named/remote branches and PRs.

## Impact
- AGENTS.md, `hermes/skills/openspec-loop-harness.md`, `docs/openspec-engineering-loop-harness.md`
  (B8 sync), the Makefile (`wt-create` / `openspec-flow` / `openspec-redeliver`), and
  `scripts/openspec-change-flow.sh` all converge on the same rule.
- B12/B26 remain valid but are now *scoped*: they describe the promotion that happens **after** the
  explicit human "deliver" instruction, not an autonomous agent decision.
