# openspec-change-flow Specification

## ADDED Requirements

### Requirement: Trigger from an OpenSpec mention
The agent MUST, when the user mentions "openspec" in a conversational request, treat it as the
trigger to start the full change lifecycle (scaffold → worktree → generate → loop → finalize →
deliver-as-PR), not merely to create a change directory.

#### Scenario: mention with a concrete intent
- **WHEN** the user sends a request containing the keyword "openspec" and describes a concrete change
- **THEN** the agent scaffolds an OpenSpec change via `make openspec-new NAME=<derived>` (which shells
  out to `openspec new change <name>`, per B15) and immediately proceeds to create a worktree and run
  the flow, rather than stopping after scaffolding.

#### Scenario: mention without an intent
- **WHEN** the user mentions "openspec" without a concrete change intent (e.g. "set up the openspec flow")
- **THEN** the agent explains the trigger is wired and awaits a concrete change name/intent before
  scaffolding a change, but does NOT require re-stating the keyword for the already-initiated flow.

### Requirement: All change artifacts confined to the worktree (never pollute the parent repo dir)
The flow MUST keep EVERY artifact of the change — the `openspec/changes/<name>/` directory, the
generated `src/main.ts` / `src/__tests__/main.test.ts`, the squashed commit, the CHANGELOG, and the
version bumps — INSIDE the dedicated worktree. The parent (default-branch) working tree MUST remain
completely untouched: no change dir, no generated TS, no new commit, no CHANGELOG/version diff.

#### Scenario: change dir lives in the worktree
- **WHEN** the flow scaffolds change `<name>`
- **THEN** it runs the scaffold from INSIDE the worktree, so `openspec/changes/<name>/` is created
  under `<worktree>/openspec/changes/<name>/` and is ABSENT from the parent repo dir.

#### Scenario: parent repo dir stays clean
- **WHEN** the flow has finished generation + finalize
- **THEN** `git status` on the parent working tree reports no new files, no new commits, and no diff
  versus the parent branch HEAD.

#### Scenario: delivery is a push, not a copy
- **WHEN** the worktree work is green and finalized
- **THEN** delivery is performed by `git push origin feat/<name>` (opens/updates the PR) and the flow
  MUST NOT copy generated TS or other files back into the parent working tree (this overrides the
  file-copy `deliver-change` model — the worktree branch IS the active branch being delivered).

### Requirement: Dedicated worktree per change
The flow MUST create a dedicated git worktree for each OpenSpec change and perform ALL generation,
verification, archive, and finalize inside it.

#### Scenario: create worktree
- **WHEN** the flow starts for change `<name>`
- **THEN** it runs `git worktree add <repo>/worktrees/<name> -b feat/<name>` and uses that worktree as
  the sole location for `make openspec-new`, `make run-agentics`, `make loop-harness`, `phase7-archive`,
  and the finalize/squash steps.

#### Scenario: rejection of parent-branch work
- **WHEN** a generation, archive, or squash step would run on the parent branch's working tree
- **THEN** the flow MUST refuse (fail-closed) and create/enter the worktree first.

### Requirement: Compose must target the worktree
The agentic, build, and loop compose containers MUST mount the worktree as their repository root
(`/project` and `/app`) so generated `src/main.ts` / `src/__tests__/main.test.ts` and the change's
`openspec/changes/<name>/` resolve inside the worktree — while `node_modules` and the `agents/`
Python pipeline sources remain bound from the main repo (they are gitignored / not in the worktree).

#### Scenario: override repoints repo mounts
- **WHEN** the flow invokes `run-agentics` / `build-app` / `test-app` / `loop-harness` for a worktree
- **THEN** it appends `docker-compose-files/worktree-override.yaml` (with `WT_ROOT` = the worktree and
  `REPO_ROOT` = the main repo) so `/project` and `/app` point at the worktree, and `node_modules` +
  `agents/agentics/src` are bound from the main repo.

#### Scenario: no-op when no worktree
- **WHEN** `WT_ROOT` is empty (no worktree flow active)
- **THEN** the override is NOT appended and compose behaviour is identical to today (no regression).

### Requirement: Loop gate is the decision point
The flow MUST run `make loop-harness` from inside the worktree and treat its real result as the gate
that decides finalize vs. fix-and-retry.

#### Scenario: green gate
- **WHEN** every loop stage passes inside the worktree
- **THEN** the flow proceeds to archive + finalize.

#### Scenario: red gate
- **WHEN** any loop stage fails
- **THEN** the flow fixes the OpenSpec spec/contract (B11 — never hand-edits generated TS), restores,
  and re-runs, bounded at ~5 attempts; if still red after ~5, it escalates (root-cause Python floor
  fix) and does NOT finalize or push.

### Requirement: Archive on green
On a green loop gate, the flow MUST archive the change (spec merge only) via `make phase7-archive
CHANGE=<name>`, run from inside the worktree, with no git commit/push (B4/B14).

#### Scenario: archive with no open tasks
- **WHEN** the loop gate is green and all `- [ ]` tasks in `tasks.md` are ticked
- **THEN** `phase7-archive` merges the spec into `<worktree>/openspec/specs/` and the change dir moves
  to `<worktree>/openspec/changes/archive/`.

#### Scenario: archive refused on open tasks
- **WHEN** any `- [ ]` task remains
- **THEN** `phase7-archive` fails closed (B16) and the flow does not finalize.

### Requirement: Finalize inside the worktree (squash confined to worktree)
The flow MUST run the finalize steps (squash → changelog → bump) from INSIDE the worktree. Squashing
is only performed inside a worktree as an AGENT/HARNESS BEHAVIOUR (the `squash-commits` script itself
is unrestricted, per explicit instruction).

#### Scenario: squash only in worktree
- **WHEN** the flow finalizes a change
- **THEN** it has already created/entered the worktree and runs `squash-commits` there; it must never
  squash on the parent branch's working tree.

#### Scenario: finalize sequence
- **WHEN** the loop gate is green, inside the worktree
- **THEN** the flow runs `squash-commits` → `changelog` → `bump-from-changelog` → `changelog-format`,
  producing one typed Conventional commit (commitlint-gated) plus a regenerated CHANGELOG and bumped
  package/manifest/versions.json — with NO push (B14). The squashed commit exists only on `feat/<name>`.

### Requirement: Deliver as a PR push (no parent pollution)
The flow MUST deliver the finished worktree branch to the remote as the PR via
`git push origin feat/<name>`, and MUST NOT modify the parent working tree.

#### Scenario: initial delivery
- **WHEN** finalize completes in the worktree and the user wants the work delivered
- **THEN** the flow runs `git push origin feat/<name>` (regular push) so the PR is created/updated;
  the parent working tree is left clean.

### Requirement: Redeliver to the same PR branch
After corrections, the flow MUST regenerate the squashed commit from the worktree and force-push to the
SAME remote PR branch (`feat/<name>`), using `--force-with-lease`, and MUST NOT rewrite `main` or any
protected ref.

#### Scenario: force-push to PR branch only
- **WHEN** the user requests a redelivery / correction after the first pass
- **THEN** the flow re-enters the worktree, regenerates/re-squashes, and runs
  `git push --force-with-lease origin feat/<name>` — and refuses if the target ref is `main` or a
  protected branch. The parent working tree remains untouched.

### Requirement: Parallel flows must not disturb each other
Multiple OpenSpec changes MUST be runnable concurrently and independently — each in its own worktree
on its own `feat/<name>` branch — without one flow disturbing another's generated files, loop run,
commits, or container resources.

#### Scenario: unique compose project per worktree
- **WHEN** more than one change flow runs at the same time
- **THEN** each flow uses a UNIQUE compose project name (e.g. `COMPOSE_PROJECT_NAME=otu-<name>` /
  `docker compose -p otu-<name>`) so container, service, and network names from different changes do
  not collide.

#### Scenario: distinct branch per worktree
- **WHEN** a worktree is created for change `<name>`
- **THEN** it is checked out on branch `feat/<name>`; git itself forbids a second worktree on the same
  branch, so concurrent flows are automatically isolated at the branch level, and commits/squashes in
  one worktree never affect another.

#### Scenario: local change dir isolation
- **WHEN** two flows run in parallel
- **THEN** each reads/writes only its own `<worktree>/openspec/changes/<name>/` and generates into its
  own `<worktree>/src/main.ts`; the agentic loader's local-change resolution never crosses worktrees.

### Requirement: B8 doc-sync stays green
The flow's documentation changes MUST keep the B8 sync docs (AGENTS.md, `openspec-loop-harness` skill,
`docs/openspec-engineering-loop-harness.md`) in agreement and `make check-docs-sync` MUST pass.

#### Scenario: sync after doc edits
- **WHEN** the flow edits any B8 sync doc
- **THEN** `make regen-doc-sync-fixtures && make check-docs-sync-and-test` is green before the change
  is archived.
