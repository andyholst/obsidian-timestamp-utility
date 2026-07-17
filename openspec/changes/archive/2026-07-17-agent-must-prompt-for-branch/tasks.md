# Tasks — Agent works in a local worktree sandbox, then AUTO-delivers the PR on completion (B27)

These tasks are the executable audit trail. Tick each box ONLY when its underlying work is done and
verified. The change records a NEW durable behaviour (B27) that reconciles the contradictory text
(`wt-create`/`openspec-flow` auto-created `feat/<name>` + pushed; Phase 5 was split between
`wt/<name>` and `feat/<name>`).

**Adopted model (per human correction):** the agent works in an isolated local `wt/<name>` sandbox
during the work; as soon as the change is COMPLETE (all tasks ticked + loop gate green + pre-commit
hook passes) it AUTOMATICALLY promotes `wt/<name>` → `feat/<name>` and opens the PR — every time, by
default, with no second "make the PR" prompt. Green-lighting a change IS the delivery authorization.

## 1. Author the spec (this change)
- [x] 1.1 Write `proposal.md` (why / what / capabilities / impact)
- [x] 1.2 Write `specs/agent-branch-governance/spec.md` in delta format (ADDED Requirements + Scenarios)
- [x] 1.3 `openspec validate agent-must-prompt-for-branch` passes

## 2. Add behaviour B27 to the B8 sync files
- [x] 2.1 Add B27 block to `AGENTS.md` (after B26): local `wt/<name>` sandbox during work;
        AUTO-promote to `feat/<name>` + open PR on completion (gates green + tasks ticked + hook
        pass); parallel-safe (unique branch + `COMPOSE_PROJECT_NAME=otu-<name>`)
- [x] 2.2 Mirror B27 into `hermes/skills/openspec-loop-harness.md`
- [x] 2.3 Mirror B27 into `docs/openspec-engineering-loop-harness.md`
- [x] 2.4 Bump the B-range literal B1–B26 → B1–B27 in all five sync sources (AGENTS.md, skill,
        harness doc, Makefile, `scripts/run-loop-harness.sh`)

## 3. Reconcile the contradictions
- [x] 3.1 Fix Phase 5 (AGENTS.md): `wt/<name>` is the standing sandbox; promotion to `feat/<name>`
        happens automatically on completion (remove the contradictory split default)
- [x] 3.2 Clarify B12: "deliver as PR" is the automatic on-completion promotion (B27), not a manual
        per-change action; the work stays in the worktree until then
- [x] 3.3 Scope B26: the post-completion push-to-own-branch latitude that B27's auto-delivery uses

## 4. Fix the Makefile + flow script defaults
- [x] 4.1 `wt-create` / `openspec-flow`: create a local `wt/<name>` sandbox by default
- [x] 4.2 `openspec-change-flow.sh`: create `wt/<name>`; AUTO-promote to `feat/<name>` + push + open
        PR on completion. `--no-push` opts out; `PUSH=1`/`--push` retained as explicit alias
- [x] 4.3 Keep parallel-safety: unique branch name + `COMPOSE_PROJECT_NAME=otu-<name>` per flow
- [x] 4.4 Make `.env` (with `GH_TOKEN`) ACCESSIBLE inside the worktree via a gitignored symlink
        (`worktrees/<name>/.env -> ../../.env`) so the agent can push + open the PR. It is NEVER
        committed/pushed (gitignored + gitleaks gate both guard it); the SSH-less token push
        resolves it first from the worktree, then the repo root.
- [x] 4.5 The `feat/<name>` push is gated TWICE: the full 10-stage `loop-harness` runs INSIDE the
        `wt/<name>` worktree (flow step 3b) BEFORE promotion, and the `git-hooks/pre-push` hook
        re-runs the hermetic `loop-collect` + `loop-unit` gate at push time. (B27 (3) push-time gate.)

## 5. Verify
- [x] 5.1 `make regen-doc-sync-fixtures && make test-check-docs-sync` — gate green (B1–B27 range)
- [x] 5.2 `make check-docs-sync` — all B8 sources agree (stage order / loop-ts-floor / B1–B27)
- [x] 5.3 `openspec validate agent-must-prompt-for-branch` passes
- [x] 5.4 Bounded proof (throwaway `b27-proof`): `make openspec-flow NAME=b27-proof` spun `wt/b27-proof`,
        ran the gate, archived, and AUTO-promoted to `feat/b27-proof` + opened PR #56 — then cleaned up
        (no stray worktree/branch; parent untouched). PR #56 closed as proof.
- [x] 5.5 `.env` accessible inside the worktree (symlink, gitignored, readable, NOT tracked) — verified
- [x] 5.6 Re-run `make openspec-flow NAME=agent-must-prompt-for-branch NO_AGENTICS=1` end-to-end:
        full gate green inside worktree, auto-promoted to `feat/agent-must-prompt-for-branch`, pushed
        via `.env` token HTTPS (no SSH), branch live on origin. PR opened.

## 6. Archive + finalize (only after 5.x green)
- [x] 6.1 `make phase7-archive CHANGE=agent-must-prompt-for-branch` (spec only) — done by the flow
- [x] 6.2 finalize in worktree: squash -> changelog -> bump-from-changelog -> changelog-format — done by the flow
- [x] 6.3 deliver as `feat/agent-must-prompt-for-branch` PR (auto, on completion per B27) — PUSHED + PR opened
