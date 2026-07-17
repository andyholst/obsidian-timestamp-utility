# Tasks

> Executable plan for the `openspec-change-worktree-flow` change. Tick each box the moment the
> underlying work is DONE + VERIFIED (B16). The final task is a real, bounded test run — not a
> meta task — and must be ticked before archiving. ALL artifacts live in the worktree; the parent
> repo dir must NEVER be touched (no change dir, no generated TS, no commit, no CHANGELOG diff).

## 1. OpenSpec scaffolding (the change of record — DONE first, gates everything)
- [x] 1.1 Scaffold the change via the real CLI: `make openspec-new NAME=openspec-change-worktree-flow` (B15) — validated green
- [x] 1.2 Write `proposal.md` (Why / What / Impact) — deep analysis of the trigger→worktree→loop→finalize→redeliver contract, with the worktree-confined invariant
- [x] 1.3 Write `specs/openspec-change-flow/spec.md` in delta format (ADDED Requirements + Scenarios, incl. "All change artifacts confined to the worktree" and "Deliver as a PR push")

## 2. Worktree plumbing (run the WHOLE flow from inside the worktree)
- [x] 2.1 Add `docker-compose-files/worktree-override.yaml`: repoint ONLY `/project` (and `integration-test-agents`' `/app`) at `WT_ROOT` (the worktree, passed via env), while KEEPING the absolute mounts already in `agents.yaml` (`REPO_ROOT/node_modules:/project/node_modules` and `REPO_ROOT/agents/agentics/src`/`/app/src`) bound from the main repo — those are absolute so they are independent of cwd. No-op when `WT_ROOT` is empty (override is only appended when set). `WT_ROOT`/`REPO_ROOT` injected via `-e` so each flow's containers target that one worktree.
- [x] 2.2 Add Makefile `wt-create` target: `git worktree add worktrees/<name> -b feat/<name>`, then symlink `node_modules` into the worktree (relative symlink `worktrees/<name>/node_modules -> ../../node_modules`; node_modules is gitignored so it lives ONLY in the worktree and never touches the parent). Wire `openspec-flow` + `openspec-redeliver` targets that set `WT_ROOT`/`REPO_ROOT` + `COMPOSE_PROJECT_NAME=otu-<name>` and shell into the worktree.
- [x] 2.3 PARALLEL-ISOLATION GUARDRAIL: each worktree flow MUST use a UNIQUE compose project name (e.g. `COMPOSE_PROJECT_NAME=otu-<name>` / `docker compose -p otu-<name>`) so concurrently-running flows (multiple spec tasks) do not collide on container/service/network names. Distinct branch `feat/<name>` per worktree is already git-enforced.

## 3. Flow driver (ALL inside the worktree; parent dir untouched)
- [x] 3.1 Implement `scripts/openspec-change-flow.sh`: create worktree FIRST → scaffold `openspec-new` INSIDE the worktree → `run-agentics` (in worktree) → `loop-harness` (in worktree, hermetic pre-flight always) → on green: `phase7-archive` (in worktree) + finalize-in-worktree (`squash-commits`→`changelog`→`bump-from-changelog`→`changelog-format`). NO file copy to parent.
- [x] 3.2 Implement `openspec-redeliver` target: re-enter worktree, regenerate/re-squash, `git push --force-with-lease origin feat/<name>`; refuse if target is `main`/protected
- [x] 3.3 Enforce "squash only from a worktree" as AGENT/HARNESS BEHAVIOUR (NOT a script limitation): the flow MUST create the worktree and run `squash-commits` inside it; document the rule in AGENTS.md + the skill. `squash-commits` itself stays unrestricted (per user instruction).
- [x] 3.4 Deliver step = `git push origin feat/<name>` (PR push) — never a file copy into the parent working tree (overrides the old `deliver-change` copy model for this flow).

## 4. Trigger wiring (the user's core ask)
- [x] 4.1 Extend `request-to-openspec` skill: when "openspec" is mentioned, scaffold AND start the worktree flow (`make openspec-flow`) rather than stopping at scaffold
- [x] 4.2 Document the trigger in `AGENTS.md` (Phase 1 / General Rules) and the `openspec-loop-harness` skill, referencing `openspec-change-flow.sh` and the "never pollute the parent dir" invariant

## 5. B8 doc-sync (MUST stay green)
- [x] 5.1 Update the B8 sync docs (AGENTS.md, `openspec-loop-harness` skill, `docs/openspec-engineering-loop-harness.md`) to describe the new worktree-confinement + force-push-to-PR-branch redelivery (B12 override), AND the new B26 behaviour (agent may commit/merge its own changes on a non-main branch when the pre-commit hook passes) — range literals bumped B1–B25 → B1–B26 across all three docs.
- [x] 5.2 `make regen-doc-sync-fixtures && make check-docs-sync-and-test` — gate green. The `drift_reorder` fixture was regenerated in-container so it matches the canonical-chain reorder detector; `check-docs-sync` GATE passes and `tests/test_check_docs_sync.py` is 33/33 green.

## 6. Verification (REAL, bounded — final task)
- [x] 6.1 Scaffold a THROWAWAY change (`readme-worktree-flow-proof`); ran `make openspec-flow NAME=readme-worktree-flow-proof NO_AGENTICS=1` which: created the worktree, scaffolded INSIDE it, ran the FULL `loop-harness` (all 10 stages PASS) inside it, archived on green, finalized (squash in worktree). Proves the flow reaches green→archive→finalize WITHOUT touching the parent repo dir.
- [x] 6.2 ASSERTED INVARIANTS (verified): (a) parent `git status` clean — only untracked `worktrees/` (gitignored); no `openspec/changes/readme-worktree-flow-proof/` leaked into parent; parent commits unchanged (2 ahead of origin/main). (b) `worktrees/readme-worktree-flow-proof` exists on `feat/readme-worktree-flow-proof` holding the squashed commit `07c0475` (archive + changelog + squash all happened inside the worktree). (c) `phase7-archive` merged the spec inside the worktree (change dir absent, spec present in `openspec/specs/`).
- [x] 6.3 Clean up the throwaway change + worktree (`git worktree remove`, delete refs/branch) so the repo is left clean
- [x] 6.4 `openspec validate openspec-change-worktree-flow` passes
