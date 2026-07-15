# Tasks

- [x] 1.1 Add `lint-commits` Makefile target: run `commitlint` over the squashed range / HEAD using `commitlint.config.cjs`
- [x] 1.2 Wire `lint-commits` into `squash-commits` as a FAIL-CLOSED gate: lint the drafted Hermes message before `git commit`; on failure run `git reset --quit <main>` and abort (no commit).
- [x] 1.3 Add `@commitlint/cli` + `@commitlint/config-conventional` to `package.json` devDependencies (pinned `^19`, committed) so the gate is hermetic.
- [x] 2.1 Add `git-hooks/commit-msg` that runs commitlint on `$1`; make it executable.
- [x] 2.2 Add `install-git-hooks` Makefile target that wires `git-hooks/commit-msg` → `.git/hooks/commit-msg`.
- [x] 3.1 Add canonical `release-flow` Makefile target: `squash-commits` → `bump-local` (Obsidian way + local tag, guarded) → `changelog` → `release-notes`. LOCAL only, no push (B14).
- [x] 4.1 VERIFY `lint-commits` passes a valid typed message: `feat(loop): add commitlint gate` piped into `node_modules/.bin/commitlint` → exit 0. (REAL RUN: passed.)
- [x] 4.2 VERIFY `lint-commits` rejects an untyped message: `bad message` → non-zero exit. (REAL RUN: passed, commitlint reports subject-empty/type-empty.)
- [x] 4.3 VERIFY `squash-commits` FAIL-CLOSED on untyped draft. PROVEN on real run: when the
      Hermes-generated draft was `'Based on the actual files, here is the squashed commit message:'`
      (untyped), `make squash-commits` printed `FAIL-CLOSED -- first line is not a typed Conventional
      commit` and `refusing to create an untyped commit` and exited 1 with NO commit created. The
      commitlint gate (1.2) correctly blocked the untyped message. ✅ DONE (real run by user).
- [x] 4.4 VERIFY `commit-msg` hook rejects a malformed manual commit: `git-hooks/commit-msg` fed `bad message` → non-zero (REAL RUN: rejected); fed a valid `feat(...)` → accepted. (Hook installed-for-real test skipped to avoid touching `.git/hooks`; script verified directly.)
- [x] 4.5 VERIFY `bump-version` GUARD basis: `git diff --quiet origin/main -- src/main.ts` is TRUE on this branch (src/main.ts unchanged vs origin/main) → guard would correctly REFUSE. (REAL RUN: confirmed unchanged.)
- [x] 4.6 VERIFY `check-released` blocks the no-gap case: proven via the same awk semver-gap logic used by `check-released` — current==latest → "does NOT advance" → would block (exit 1). (REAL logic check; live `gh` network call is human-only.)
- [x] 4.7 VERIFY `release-flow` sequencing (throwaway worktree): ran `make release-flow PART=patch` in a
      throwaway worktree (B24). It revealed a FAIL-OPEN defect -- `changelog` errored (exit 1) yet the
      flow printed "COMPLETE" with the version UNBUMPED (still 0.4.10, no `## 0.4.11`, versions.json
      missing 0.4.11). FIXED: added `set -e;` to the `release-flow` / `release-prep` / `loop-release` /
      `bump-local` recipe chains so ANY step failure aborts the whole flow (fail-closed). Re-verified:
      `make release-prep PART=patch` now STOPS at `check-released` (0.4.10 already released) and leaves
      the version unbumped -- correct fail-closed behaviour. The flow also requires `node_modules`
      (openspec CLI) present; run it from the parent checkout, not a bare worktree. ✅ DONE.
- [x] 5.1 B8-sync: update AGENTS.md (B22) to document `lint-commits`, the `commit-msg` hook, and the canonical `release-flow` order (squash → bump-local → changelog → release-notes). NOTE: the mirror skill `hermes/skills/openspec-loop-harness/references/release-automation-loop-stage.md` lives in a DIFFERENT profile's read-only tree (cross-profile write guard refused); a reference addendum describing the new targets is recommended but must be applied by the user or with explicit cross-profile consent. AGENTS.md (the repo's authoritative source) + this change's spec are synced.
- [x] 6.1 VERIFICATION: `make loop-collect` + `make loop-unit` still pass (hermetic). VERIFY (real host):
      `make loop-collect` -> 525 collected exit 0; `make loop-unit` -> 525 passed exit 0. The
      Makefile/package.json/hook changes touch NO agent Python, so no regression. ✅ DONE.
- [x] 7.1 `openspec validate enhance-squash-commits` passes. `openspec` is an npm devDependency
      (`@fission-ai/openspec`); ran `openspec validate enhance-squash-commits` -> "Change
      'enhance-squash-commits' is valid". ✅ DONE.
