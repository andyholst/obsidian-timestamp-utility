# Tasks: `make commit` — thorough Angular commit vs `main`, squashed into one

- [x] 1.1 Rewrite the `commit` Make target so the diff base is `origin/main`
      (fallback `main`), not the upstream tracking branch.
- [x] 1.2 Pass Hermes (project-manager) the changed-file list + `git diff --stat`
      vs `main`, and instruct it to write a THOROUGH Angular title + body that
      describes the real behavioural changes in the substantive files (loop-harness
      engineering, code_integrator floor, agentic pipeline, Makefile / compose /
      Containerfile changes, merged OpenSpec specs) — not meta commentary.
- [x] 1.3 Squash via `git reset --soft <main> && git commit -m "<msg>"` into ONE
      commit; never push (B14).
- [x] 1.4 On empty Hermes message: `git reset --quit <main>` restores pre-squash
      state and aborts (no empty/partial commit).
- [x] 1.5 Run `make commit`; verify ONE commit ahead of `main`, clean tree, thorough
      human-readable message; `git show` reviewed. No push.
- [x] 1.6 Run `openspec validate loop-commit-squash`; then
      `make phase7-archive CHANGE=loop-commit-squash`.
