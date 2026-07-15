# Proposal: `make loop-harness` / `run-loop-harness.sh` — verbose, live-streamed terminal output

## Why
When the user runs `make loop-harness` (or `bash scripts/run-loop-harness.sh`), the
current wrapper silences every stage: `run_stage` redirects `make <stage>` output to
`/tmp/loop_<stage>.log` and only prints `=== <stage> (timeout Ns) ===` then `-> PASS`.
Consequences the user hit:
- A stage that finishes in 2s (`loop-build-app`) looks like it "went super quick" with no
  evidence of what ran — no rollup/jest/pytest output is visible.
- During a long stage (e.g. `loop-integration`, 1500s) the terminal is silent, so it is
  impossible to tell whether the loop is progressing or hung.
- The only way to see what happened is to open a separate log file after the fact.

The harness must be **observable in real time**: stream each stage's `make` output to the
terminal as it runs (so rollup/jest/pytest lines appear live), show a start banner with a
timestamp and what is being executed, and print a clear PASS/FAIL/TIMEOUT/timeout line per
stage. Keep the log file as a backup, but the terminal is the primary surface.

## What Changes
- `scripts/run-loop-harness.sh` `run_stage`: replace the silent `> log 2>&1` redirect with a
  live `tee` to BOTH the terminal and `/tmp/loop_<stage>.log`. Add a stage start banner
  (timestamp + the docker-compose service / command the stage drives) and a per-stage
  elapsed-time + result line. Optionally a lightweight progress indicator (e.g. a dot every
  few seconds) so a quiet stage still shows life.
- Keep behaviour identical otherwise: seven stages in order, per-stage `timeout` caps,
  surgical container teardown, non-zero exit on any red gate.

## Capabilities
- `loop-harness-verbose-output` (new) — see `specs/loop-harness-verbose-output/spec.md`.

## Impact
- The user can watch real progression (rollup build, jest tests, pytest collection/run) as it
  happens and immediately see which stage is active and how long it took. No more "is it stuck?"
  ambiguity. The log files remain for post-hoc debugging.
