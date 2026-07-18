# Tasks: release-dryrun-loop-gate

- [x] 1. Create the OpenSpec change via `openspec new change` (B15) and validate.
- [x] 2. Create an implementation worktree `wt/release-dryrun-loop-gate`.
- [x] 3. Add a `loop-release-dryrun` Makefile target that runs through docker + make
      (containers/npm node image): build the plugin, run jest (test-app), run
      `scripts/release.sh` DRY_RUN=1, and assert the zip contains `main.js`. No
      GitHub API call (B14).
- [x] 4. Rewrite `scripts/release.sh` to PACKAGING-ONLY (assumes `dist/main.js` built
      by `make build-app`; no inline rebuild) and make `make release` depend on
      `build-app`. The docker+make gate runs `release.sh DRY_RUN=1` inside the
      containers/npm image and asserts `main.js` in the zip.
- [x] 5. Add `loop-release-dryrun` to the canonical stage order in
      `scripts/run-loop-harness.sh` (after loop-build-app/loop-test-app, before
      loop-release-tests) and in the B8 sync docs (AGENTS.md, hermes skill,
      docs/openspec-engineering-loop-harness.md, Makefile header comment).
- [x] 6. Add durable behaviour **B33** (release packaging is a hermetic, no-publish
      docker+make loop gate) and **B34** (no merge/force-push until the human approves
      via a PR comment) across the B8 sync set; bump the B-range string to B1-B34.
- [x] 7. `openspec validate release-dryrun-loop-gate` passes.
- [x] 8. Run `make loop-release-dryrun` on the host (docker + make) and confirm it
      builds + tests + produces a zip with `main.js`, with NO GitHub call — GREEN.
- [x] 9. Run `make check-docs-sync` and confirm PASS (B1-B34 range agreed).
- [x] 10. (Verification) `openspec validate release-dryrun-loop-gate` passes AND
      `make loop-release-dryrun` exits 0 with the zip containing main.js AND
      `make check-docs-sync` passes.
