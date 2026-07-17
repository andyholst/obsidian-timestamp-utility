# Proposal: OpenSpec Change → Worktree → Loop → Finalize Flow

## Why

Today the OpenSpec loop-harness tooling exists in pieces (`openspec-new`, `run-agentics`,
`loop-harness`, `phase7-archive`, `loop-finish`) but there is **no single, agent-driven flow** that
ties them together the way the user wants to operate:

1. **An OpenSpec change is the trigger.** When the user mentions "openspec" in a request, the agent
   must scaffold a change (the `request-to-openspec` intake gate) and then — instead of stopping —
   drive the *whole* lifecycle.
2. **Always work from a worktree, and NEVER pollute the parent repo dir.** Every artifact of the
   change — the `openspec/changes/<name>/` directory, the generated `src/main.ts` /
   `src/__tests__/main.test.ts`, the squashed commit, the CHANGELOG / version bumps — MUST live ONLY
   inside a dedicated git worktree (`feat/<name>`). The parent branch's working tree MUST remain
   completely untouched: no change dir, no generated TS, no commit, no CHANGELOG diff. Delivery to the
   branch happens by **pushing the worktree's branch as the PR**, not by copying files back into the
   parent working tree.
3. **Run the harness / loop engineering.** The change is only "done" when `make loop-harness` is
   green (B20 mandatory pre-flight), run from inside the worktree.
4. **On green: archive + finalize (in the worktree).** Archive the change (`phase7-archive`, spec
   merge only — B4/B14) inside the worktree, then finalize (`loop-finish` = squash → changelog →
   bump). **Squashing is only performed inside the worktree** — this is an *agent/harness behaviour*
   constraint (the script itself is unrestricted).
5. **Corrections → redeliver to the SAME PR branch.** If changes are needed after the first pass,
   the flow regenerates (new squashed commit from the worktree) and **force-pushes to the same PR
   branch** so the PR updates in place. The user explicitly accepts force-push **to that branch
   only** (PR branches are rebased, never preserved — never protected branches like `main`).

The user's final instruction for this change: *wire the trigger now, then TEST it* — i.e. when the
user mentions "openspec" in the conversation, the agent starts this process, creates the worktree,
and exercises it end-to-end with a throwaway change, **without ever touching the parent repo dir**.

## What Changes

A new agent-driven flow (`make openspec-flow NAME=<name>` / `scripts/openspec-change-flow.sh`) with
this contract:

- **Create worktree FIRST**: `git worktree add <repo>/worktrees/<name> -b feat/<name>` (the isolated
  sandbox). Nothing is written to the parent working tree.
- **Scaffold INSIDE the worktree** (B15 still holds — the directory is produced by `openspec new
  change`, never hand-written; it just runs from inside the worktree so the change dir lives there):
  `cd <worktree> && make openspec-new NAME=<name>` → `<worktree>/openspec/changes/<name>/`.
- **Generate + verify inside the worktree**: point the agentic / build / loop compose containers at
  the worktree via a compose override (`docker-compose-files/worktree-override.yaml`) that repoints
  `/project` (and `/app`) at the worktree but keeps `node_modules` + the `agents/` Python sources
  bound from the main repo (those are gitignored / not checked out in a worktree). Run
  `make run-agentics` then `make loop-harness` **from inside the worktree**.
- **Loop gate decides**: green → finalize; red → fix spec (B11), re-run, bounded ~5 attempts.
- **On green → finalize (worktree-only)**:
  1. `make phase7-archive CHANGE=<name>` — archive the spec (worktree only, no git commit/push — B4/B14).
  2. Inside the worktree: `make loop-finish` (archive-all → `squash-commits` → `changelog` →
     `bump-from-changelog` → `changelog-format`). **Squashing happens only here, in the worktree.**
  3. **NO file copy back to the parent.** The deliverable reaches the branch by
     `git push origin feat/<name>` (opens/updates the PR). The parent working tree stays clean.
- **Redeliver after corrections**: `make openspec-redeliver NAME=<name>` re-enters the worktree,
  regenerates / re-squashes, and **force-pushes `feat/<name>` to the same remote PR branch**
  (`git push --force-with-lease origin feat/<name>`). Never force-pushes `main` or any protected ref.

## Capabilities

- `openspec-change-flow` (new): the end-to-end agent-driven lifecycle that, given an OpenSpec change,
  creates a worktree, runs generation + the loop gate, archives on green, and finalizes + redelivers
  to the same PR branch — with ALL artifacts confined to the worktree and squashing never leaving it.

## Impact

- **MUST NOT regress**: B1 (persistent e2e harness), B4/B14 (no git commit/push from the loop /
  archive steps), B10/B11 (spec is single source of truth — fix the spec, never generated TS),
  B15 (change dir created only via `openspec new change`), B19 (archived change dirs carry a
  `YYYY-MM-DD-` prefix — resolvers/tests must handle it), B20 (loop gate is a mandatory pre-flight),
  B23 (never let committed fix-work die under a `git reset --hard` — commit finalize fixes before
  re-running).
- **NEW invariant (overrides B12's file-copy model for this flow)**: the change + generated TS +
  squashed commit + CHANGELOG live ONLY in the worktree; the parent repo dir is never modified.
  Delivery = push the worktree branch (`feat/<name>`) as the PR, not a file copy into the parent
  working tree. B12 is updated in the B8 sync docs to reflect this (the worktree branch IS the active
  branch being delivered; a file copy into the parent would re-introduce pollution).
- **New behaviour**: squashing is *only* performed inside a worktree (agent/harness behaviour — the
  `squash-commits` script itself stays unrestricted, per user instruction). Branch for the worktree
  is `feat/<name>`.
- **Force-push scope**: restricted to the worktree's own PR branch via `--force-with-lease`; guarded
  against `main`/protected refs so a misconfiguration can never rewrite shared history.
- **B8 sync**: this change edits the B8 sync docs (AGENTS.md, `openspec-loop-harness` skill,
  `docs/openspec-engineering-loop-harness.md`) to describe the new flow; fixtures must be regenerated
  and `check-docs-sync` must stay green.
- **Verification**: the final task is a REAL bounded run — scaffold a throwaway change, create the
  worktree, run the *hermetic* loop gates inside it, and prove the flow reaches "green → archive →
  finalize + PR push" while `git status` on the PARENT stays clean (no change dir, no commits, no
  generated TS). Heavy stages (Ollama) are exercised only if the host has a live Ollama; hermetic
  gates must always pass.
