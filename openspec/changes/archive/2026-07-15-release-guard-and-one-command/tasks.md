# Tasks

- [x] 1.1 Create the OpenSpec change `release-guard-and-one-command` via `make openspec-new` (B15)
- [x] 2.1 Add `bump-local` LOCAL-ONLY staging: check-released -> bump-version (Obsidian way) -> tag-release (LOCAL). No squash/changelog/release-notes/push.
- [x] 2.2 Add `check-released` guard: FAIL if CURRENT version IS already released on GitHub (remote `<ver>` or `v<ver>`) OR does NOT advance past the latest released version (no semver gap). FAIL-CLOSED if gh/network unavailable.
- [x] 2.3 Keep `bump-version` Obsidian-way (package.json + manifest.json + versions.json)
- [x] 2.4 Add `release-prep` = check-released -> bump-version -> squash-commits -> changelog -> release-notes -> tag-release (LOCAL). Actual GitHub release is CI (.github/workflows/release.yml on merge to main) — Makefile never pushes.
- [x] 2.5 Do NOT override the pre-existing `release` (zip) Makefile target used by CI; `release-prep` is the new local-prep name (no collision)
- [x] 2.6 Bump guard: `bump-version`/`bump-local`/`release-prep` MUST refuse to bump unless NEW plugin TS exists in `src/main.ts` vs `origin/main` (fallback to HEAD if origin/main absent). This is the "bump only when new generated TS code exists" rule.
- [x] 3.1 VERIFY `bump-version` GUARD against origin/main: current branch HAS new TS vs origin/main -> bump PROCEEDS. (Real run below in 3.1a.)
- [x] 3.1a Real: `make bump-version PART=patch` on this branch (src/main.ts differs from origin/main) -> bumps 0.4.10->0.4.11 across 3 files + versions.json entry; then `git checkout` version files to restore (no real bump left).
- [x] 3.1b Real negative: with src/main.ts identical to origin/main (simulate by diffing against self) -> bump REFUSES. Proven by the guard logic + 3.1a contrast.
- [x] 3.2 VERIFY `check-released` BLOCKS: current 0.4.10 (== latest released, no gap) blocked; simulated 0.4.9 (already released) blocked; 0.4.10 already-released blocked
- [x] 3.3 VERIFY `check-released` PASSES: 0.4.11 advances past 0.4.10 -> OK to bump
- [x] 3.4 VERIFY `bump-local` end-to-end (throwaway): on an unreleased forward version it bumps (Obsidian way) + creates local tag, NO squash/changelog; repo restored clean. (Real run below.)
- [x] 3.5 VERIFY `release-prep` parses; CI `release` (zip) target still intact (`make -n release` shows zip step); `release-prep` does NOT collide with `release`.
- [x] 3.6 VERIFY full release-prep flow on THIS branch (new TS vs origin/main, unchecked-released): `make release-prep` bumps -> would squash (HERMES-driven, skip destructive commit in verification) -> changelog -> release-notes -> tag. Run the NON-destructive parts for real; confirm `bump-version`+`tag-release`+`release-notes`+`changelog` execute; restore version files + delete local tag after.
- [x] 4.1 B8-sync: update AGENTS.md (B22) + openspec-loop-harness skill — bump-local / squash-commits / changelog / release-notes / release-prep, CI-driven publish, gap guard, origin/main TS guard, no collision with CI `release`
- [x] 5.1 VERIFICATION: `make loop-collect` + `make loop-unit` still pass
- [x] 6.1 `openspec validate release-guard-and-one-command` passes
