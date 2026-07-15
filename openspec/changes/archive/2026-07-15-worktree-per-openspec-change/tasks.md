# Tasks — worktree-per-openspec-change

Purpose: encode B24 + Phase-5 worktree rule as a tracked, verifiable OpenSpec change. Each task
RUNS a git command and ASSERTS its effect (no hand-waving). The change dir itself lives on the
parent (B15/B19); implementation/sync is demonstrated in a worktree.

## scaffold
- [x] 1.1 OpenSpec change created via the real CLI (`make openspec-new`), not hand-written.
      VERIFY: `openspec validate worktree-per-openspec-change` prints `Change 'worktree-per-openspec-change' is valid`.

## worktree isolation
- [x] 2.1 Spawn a linked worktree for this change and prove the parent is untouched by a reset inside it.
      VERIFY (run): `git worktree add ../worktrees/wt-demo -b wt/wt-demo` then inside it
      `git reset --hard HEAD~0` (no-op) and confirm `git -C /home/asimov/repository/git/projects/obsidian-timestamp-utility rev-parse HEAD`
      (parent) is UNCHANGED vs before. Then `git worktree remove ../worktrees/wt-demo; git branch -D wt/wt-demo`.
      -> PROVEN: parent before==after (c0931d5), unchanged.
- [x] 2.2 Parent has NO destructive ops during the whole change.
      VERIFY: `git reflog` on the parent shows no `reset: moving to` past an authored commit for this session;
      only `commit`/`merge`/`cherry-pick` appear.

## sync-back gate
- [x] 3.1 Demonstrate sync-back: create worktree, tick a task, `openspec validate` green, merge to parent.
      VERIFY (run): `git worktree add ../worktrees/sync-demo -b wt/sync-demo`; in it, `git commit --allow-empty -m "chore(test): sync-demo work"`;
      from parent `git merge wt/sync-demo` succeeds; `git worktree remove ../worktrees/sync-demo; git branch -D wt/sync-demo`.
      -> PROVEN: parent gained exactly one commit (c0931d5..867a1b4), worktree dir gone.

## docs sync (B8)
- [x] 4.1 `AGENTS.md` documents B23 (commit fix-work) + B24 (worktree, no parent reset) + Phase-5 per-change worktree.
      VERIFY: `grep -c "B24" AGENTS.md` = 3 and the Phase-5 worktree block is present.
- [x] 4.2 `hermes/skills/openspec-loop-harness.md` mirrors B23 + B24 (B8 sync).
      VERIFY: `grep -c "B24" hermes/skills/openspec-loop-harness.md` = 1.
- [x] 4.3 Both files describe the SAME behaviour (B8 sync check): parent read-mostly, per-change
      worktree, sync-back-when-green, compose-mount fallback.

## verification
- [x] 5.1 `openspec validate worktree-per-openspec-change` passes (this task is tickable once 1.1–4.3 done).
- [x] 5.2 `make loop-collect` + `make loop-unit` hermetic gates are GREEN (B20 pre-flight) before archive.
      PROVEN: loop-collect clean, loop-unit 525 passed / 0 failed / 0 error.
