# Change: release-dryrun-loop-gate

## Why

The 0.4.16 release shipped a GitHub Release whose downloadable zip was missing
the compiled plugin (`dist/main.js`) — the build silently failed in CI and the
zip was packaged without it. We already fixed the build resolution
(`scripts/release.sh` now walks up for `node_modules/.bin/rollup` and requires a
successful build). But there was **no hermetic gate** that proves, on every loop
run, that a release dry-run produces a zip containing `main.js` — without ever
calling the GitHub release API.

Today the release dry-run tests (`tests/test_release_pipeline_dryrun.py`,
`tests/test_release_build_rollup.py`) run host-side via pytest and only exercise
`scripts/release.sh` in a copied repo. They are NOT part of the containerised loop
harness (the docker+make path), so the loop can go green while the *packaging* is
broken. The user requires the release packaging to be a first-class, docker+make,
no-publish loop gate — exactly like `build-app`/`test-app` are gates.

## What Changes

- Add a new loop stage `loop-release-dryrun` that runs **through docker + make**:
  it builds the plugin (same `containers/npm` image `build-app` uses), runs the
  jest tests (`test-app`), then runs `scripts/release.sh` in **DRY_RUN=1** mode
  inside the container and **asserts the produced zip contains `main.js`**. It
  never calls the GitHub release API (B14: no publish from the loop).
- The gate uses the existing `containers/npm` node image (node:22 + zip + git +
  rollup) so the build runs exactly as it would in CI.
- Make the existing `tests/test_release_build_rollup.py` regression test runnable
  from inside that container via `make loop-release-dryrun` (it already uses
  `DRY_RUN=1` and makes no network calls).
- Add a durable behaviour **B33** ("release packaging is a hermetic, no-publish
  loop gate") so this gate is never dropped and the loop cannot go green while
  the release zip would ship without `main.js`.

## Capabilities

- `release-pipeline` (modified): the release artifact set MUST include the
  compiled `main.js`; the build is REQUIRED; and the packaging is verified by a
  hermetic docker+make loop gate (no GitHub publish from the loop).

## Impact

- Loop gate order gains `loop-release-dryrun` after `loop-build-app` /
  `loop-test-app` (the natural "release dry-run" step) and before
  `loop-release-tests` (the python doc/note assertions).
- No change to the actual publish path (`release.yml` still publishes on merge to
  main). This change only adds a *local* verification gate.
