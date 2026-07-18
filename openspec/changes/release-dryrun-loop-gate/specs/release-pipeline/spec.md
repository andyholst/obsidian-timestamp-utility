# Spec: release-pipeline (release-dryrun-loop-gate)

## ADDED Requirements

### Requirement: Release packaging is a hermetic docker+make loop gate

The system MUST provide a loop stage `loop-release-dryrun` that verifies the
release artifact set WITHOUT publishing. It MUST run through docker + make (the
same `containers/npm` node image used by `build-app`), build the plugin, run the
plugin tests, then run `scripts/release.sh` in `DRY_RUN=1` mode and assert the
produced zip contains the compiled `main.js`. It MUST NOT call the GitHub release
API (no publish from the loop — B14).

#### Scenario: release dry-run produces a zip containing main.js

- **WHEN** `make loop-release-dryrun` runs inside the loop harness
- **THEN** the plugin is built (dist/main.js produced), the jest tests pass, and
  `scripts/release.sh` (DRY_RUN=1) produces `<REPO_NAME>-<TAG>.zip` whose member
  set includes `main.js`, with NO GitHub release API call made

#### Scenario: broken build fails the gate

- **WHEN** the plugin build fails (no dist/main.js)
- **THEN** `scripts/release.sh` exits non-zero and `make loop-release-dryrun`
  fails the loop run (so a broken release is caught before any publish)

## MODIFIED Requirements

### Requirement: Release artifact set includes the compiled plugin

The release artifact set MUST include the compiled `main.js`. The build is
REQUIRED (the zip must ship the compiled plugin); if the build fails the release
is aborted rather than shipping an empty zip. This MUST be verified by the
hermetic `loop-release-dryrun` gate on every loop run.

#### Scenario: zip ships main.js

- **WHEN** a release dry-run completes
- **THEN** the zip contains `main.js` (the compiled plugin), `manifest.json`,
  `README.md`, `CHANGELOG.md`, and `release_notes.md`
