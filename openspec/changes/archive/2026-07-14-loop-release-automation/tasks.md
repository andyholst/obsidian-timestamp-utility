# Tasks

- [x] 1.1 Create the OpenSpec change `loop-release-automation` via `make openspec-new` (B15)
- [x] 2.1 Add `bump-version` Makefile target: bumps `package.json` + `manifest.json` `version`, appends `<new>: <minAppVersion>` to `versions.json`; `PART=patch|minor|major` (default patch)
- [x] 2.2 Add a "## Release / Changelog" section to `README.md` documenting the version-bump + tagged, sectioned changelog flow (mirrors the git_chglog categories); preserve README format
- [x] 2.3 Reuse the existing `changelog` target so regenerated `CHANGELOG.md` is SECTIONED by commit type (feat/fix/refactor/docs/chore) — driven by the squashed commit's Conventional `type(scope):` prefix
- [x] 2.4 Add `tag-release` Makefile target: local `git tag v<version>` (NO push, B14), invoked AFTER `squash-commits`
- [x] 2.5 Add `loop-release` (post-green) target: runs ONLY after `loop-test-app` green AND only when `src/main.ts`/`src/__tests__/main.test.ts` changed vs committed baseline → bump-version → squash-commits → changelog → release-notes → tag-release. The 7-stage `loop-harness` verification order stays UNCHANGED.
- [x] 4.5 Harden `squash-commits`: FORCE a valid Conventional `type(scope):` first line and FAIL-CLOSED if Hermes returns an untyped message (so the changelog sections + version bump get a reliable tag) — this is the "tag the commit accordingly" requirement
- [x] 3.1 VERIFY `bump-version` (throwaway): patch → `0.4.11` across the 3 files + `versions.json` entry; `PART=minor` → `0.5.0`; then `git checkout` version files to restore (no real bump)
- [x] 3.2 VERIFY `tag-release` logic: local `v<version>` tag created, NO `git push` (B14)
- [x] 3.3 VERIFY `loop-release` guard: unchanged `src/main.ts` → no-op (no bump/tag)
- [x] 3.4 VERIFY changelog sectioning: a Conventional-typed squashed commit yields categorized sections in `CHANGELOG.md` (verified the chglog/config.yml grouping + that squash-commits now forces the typed prefix that drives it)
- [x] 4.1 B8-sync: document the new post-green release stage (B22) in AGENTS.md + openspec-loop-harness skill
- [x] 5.1 VERIFICATION: `make loop-collect` (0 errors) + `make loop-unit` (pass) still green
- [x] 6.1 `openspec validate loop-release-automation` passes
