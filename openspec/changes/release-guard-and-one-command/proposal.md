# Proposal: ReleaseGuardAndOneCommand

## Why

The previous `loop-release-automation` change added the building blocks (`bump-version`,
`squash-commits`, `changelog`, `release-notes`, `tag-release`, `loop-release`) but the user wants
two concrete guarantees:

1. **One easy command.** It must be trivial to "squash the commit, tag it accordingly, and bump to
   a new version — the Obsidian way" in a single invocation, not five separate targets.
2. **Never re-release an already-released version.** If the current `package.json` version is
   ALREADY published to the GitHub project repo (i.e. its tag exists in the remote), the flow MUST
   REFUSE to bump/tag — bumping an already-released version would create a duplicate GitHub release
   and corrupt the plugin's version history. The guard must tolerate the repo's historical tag
   inconsistency (both `0.4.8` and `v0.4.9` forms exist remotely).

## What Changes

- Add a single **`release`** Makefile target that performs, in order:
  `check-released` (guard) → `bump-version` (Obsidian way) → `squash-commits` (typed Conventional
  commit, fail-closed) → `changelog` (sectioned CHANGELOG.md) → `release-notes` (README block) →
  `tag-release` (local tag). This is the **publish** command: it assumes the version is already
  bumped/tagged locally and produces the squashed, categorized, tagged release (local only, no push).
- Add **`bump-local`** — a LOCAL-ONLY staging command: `check-released` → `bump-version` →
  `tag-release`. It bumps the Obsidian version (package.json + manifest.json + versions.json) and
  creates a LOCAL tag, WITHOUT `squash-commits`, WITHOUT `changelog`, and WITHOUT `release-notes`.
  This is how the user advances the version and tags it locally first ("bump tag version, squash
  commits accordingly, do changelog update locally, THEN run the release command").
- Add **`check-released`** guard: FAIL if the CURRENT `package.json` version is already released on
  GitHub (remote tag `<version>` OR `v<version>`, tolerant of both forms); FAIL-CLOSED if `gh`/
  network unavailable. Wired into `release` and `bump-local` (and `loop-release`) BEFORE bumping.
- Typical local workflow the user runs:
  1. `make bump-local PART=patch`  → bump version + local tag, staged locally.
  2. (do the work / let the loop-harness verify) → `make squash-commits` produces the typed commit;
     `make changelog` updates CHANGELOG.md; `make release-notes` updates README.
  3. `make release`  → the publish command: re-checks not-already-released, and (since version files
     are already bumped) it refreshes changelog/notes and creates the local tag — the release artifact.
  Pushing commit + tag remains a deliberate human action (`git push` / `git push origin v<version>`).

## Capabilities

- `release-automation` (extends existing): adds the single-command `release` entry point + the
  already-released GitHub guard.

## Impact

- Touches `Makefile` only (new `release` + `check-released` targets) plus this change's
  proposal/spec/tasks. No agent logic, no B1–B21 regressions. B14 still holds: `release` creates a
  LOCAL tag and squashes locally; pushing commit + tag remains a deliberate human step.
- The 7-stage `loop-harness` verification gate is unchanged; `release`/`check-released` are outside it.
