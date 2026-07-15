# Proposal: LoopReleaseAutomation

## Why

Today the agentic pipeline can generate new TypeScript code + tests for the plugin, and the
loop-harness (`make loop-harness`, 7 stages) proves they are green. But the **release side of that
success is entirely manual**: bumping the Obsidian plugin version, tagging, writing the CHANGELOG,
and updating the README all happen by hand (or not at all). The user wants release automation to
be a **first-class part of loop engineering**: when the loop is green after new generated TS code
is produced, the repo must (1) bump the plugin version the Obsidian way, (2) update the README
release notes, (3) regenerate the CHANGELOG, (4) squash the commits into one, and (5) tag the
release — in that order, with no push (B14).

This closes the gap where "the loop is green" did not automatically become "a versioned, tagged,
documented release candidate."

## What Changes

- **Obsidian version bump (the real Obsidian way).** Add a `bump-version` Makefile target that
  bumps `package.json` `version`, `manifest.json` `version`, and **appends the new version →
  `minAppVersion` mapping to `versions.json`** (the Obsidian `versions.json` convention the repo
  already uses — see current `versions.json` mapping every `0.x.y` → `0.15.0`). Bump strategy:
  patch by default, with `PART=minor|major` override. No rewrite of history; the version files are
  the source of truth (mirrors how `TAG := $(shell node -p "require('./package.json').version")`
  already derives the zip tag).
- **README release-notes update.** A `release-notes` step (or part of `record-work`) refreshes a
  "## Release / Changelog" area of `README.md` so the documented version + recent changes are
  true. The README keeps its existing format/headings.
- **CHANGELOG regeneration.** Reuse the existing `changelog` target (`git_chglog` → `CHANGELOG.md`)
  as a stage in the release flow.
- **Squash + tag.** After the loop is green and version bumped: run `squash-commits` (existing
  target — one Angular commit, no push, B14) then `git tag v<version>` (local tag only, still no
  push — B14). A new `tag-release` target wraps the local tag.
- **Wire into loop engineering.** Add a `loop-release` stage (or a `loop-post-green` target) that
  runs **only after `loop-test-app` is green** and only when new generated TS was actually
  produced (guard: skip if `src/main.ts` / `src/__tests__/main.test.ts` are unchanged vs the last
  committed baseline, so docs-only or no-op runs don't mint a version). It performs:
  bump-version → release-notes → changelog → squash-commits → tag-release. The 7-stage
  `loop-harness` stays the verification gate (unchanged); `loop-release` is the **post-green
  release stage** invoked by `make loop-trigger` (B20) sequence or explicitly, never silently.

## Capabilities

- `release-automation` (new): version bump (Obsidian way) + README release-notes + CHANGELOG +
  squash + local tag, wired as a post-green loop-engineering stage, all no-push (B14).

## Impact

- Touches `Makefile` (new targets), `README.md` (release-notes section), and the version files
  (`package.json`, `manifest.json`, `versions.json`). No change to the deterministic floor or the
  7 verification stages (B4/B14 still hold: no git **push**; tagging is local only).
- MUST NOT regress: `make loop-unit` / `make loop-collect` still green; the 7-stage
  `loop-harness` verification order is unchanged.
- Durable behaviours preserved: B4/B14 (no commit/push from the loop — `squash-commits` and
  `tag-release` only write locally; pushing remains a deliberate human step), B11 (generated TS is
  never hand-edited — version bump is metadata only).
