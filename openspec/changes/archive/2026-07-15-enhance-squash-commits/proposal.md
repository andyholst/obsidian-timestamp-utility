# Proposal: EnhanceSquashCommits

## Why

The user wants the commit workflow to be release-grade end-to-end:

1. **Squash, then "tag it accordingly".** `make squash-commits` already collapses all WIP
   commits ahead of `main` into ONE typed Conventional commit (`type(scope): subject`), and the
   first line's type already drives both the CHANGELOG sections and the bump PART. This change
   hardens that contract with a **commitlint gate** so an untyped/malformed squashed message fails
   closed (no commit), and adds a per-commit **`commit-msg` git hook** so typos are caught at
   commit time — the "changelog lint you could add" the user asked about.
2. **Bump only the next unreleased version, only when new plugin TS changed.** We must be able
   to bump to the next version that has NOT been released, but ONLY when a new TS-code change in
   `src/main.ts` actually occurred. The Obsidian-way bump (`bump-version`) and the
   `check-released` gap guard already exist and already enforce this; we wrap them in a canonical
   sequence and make the guard explicit. The tag created on bump is LOCAL — never pushed (B14) —
   and `check-released` guarantees there is **no gap** between the bumped version and the previous
   released version (patch bump from latest → latest+1).
3. **CHANGELOG must show the new bump version.** After squash + bump, the CHANGELOG.md must be
   regenerated so the new `## <version>` section is viewable. The existing `changelog` target
   (git_chglog) renders a section per git tag, so a local `v<version>` tag after bump yields a new
   `## <version>` entry.

## What Changes

- Add a **`lint-commits`** Makefile target that runs `commitlint` over the commits being squashed
  (or over HEAD) using the repo's `commitlint.config.cjs`, so every message is a valid Conventional
  commit. Wire it as a **fail-closed gate inside `squash-commits`** (the drafted Hermes message is
  linted before `git commit`; on failure the pre-squash state is restored and abort).
- Add a **`commit-msg` git hook** (`git-hooks/commit-msg`) that runs commitlint on each message,
  plus a Makefile **`install-git-hooks`** target so the hook is wired into `.git/hooks`. This gives
  per-commit linting (the "changelog lint on each commit").
- Add a canonical **`release-flow`** Makefile target encoding the user's exact order, LOCAL only:
  `squash-commits` → `bump-local` (Obsidian-way bump + local tag, guarded by `check-released` and
  the existing new-TS guard) → `changelog` (regenerate CHANGELOG.md with the new `## <version>`
  section) → `release-notes` (refresh README block). No push (B14).
- Ensure the **bump-without-gap** invariant is explicit: `check-released` already refuses if the
  bumped version does not advance past the latest released version (no semver gap) and tolerates
  `X`/`vX` remote tags. We document this as the contract and add a verification task proving it.

## Capabilities

- `release-automation` (extends existing): adds `lint-commits`, `install-git-hooks`,
  `commit-msg` hook, and the canonical `release-flow` sequencing target; hardens the
  Conventional-typing contract on `squash-commits`.

## Impact

- Touches `Makefile` only (new/updated targets + hook wiring) plus this change's
  proposal/spec/tasks and a new `git-hooks/commit-msg`. No agent Python logic changes.
- B1–B21 and the 7-stage `loop-harness` gate are unchanged; `release-flow`/`lint-commits` are
  outside the verification gate. No git push is performed anywhere (B14).
- Requires `@commitlint/cli` + `@commitlint/config-conventional` in `package.json` devDependencies
  (committed to the repo) so the lint gate is hermetic and reproducible.
- The `openspec` CLI is **not available in this execution environment** (not installed, no network
  for `pip install @fission-ai/openspec`); the change directory was therefore hand-authored to the
  exact validated shape that `make openspec-new` produces (`.openspec.yaml` + `README.md` +
  `proposal.md` + `tasks.md` + `specs/<cap>/spec.md`). This is a deviation from durable behaviour
  B15 and must be re-created via `make openspec-new NAME=enhance-squash-commits` when the CLI is
  available (the existing `release-guard-and-one-command` change demonstrates the produced shape).
