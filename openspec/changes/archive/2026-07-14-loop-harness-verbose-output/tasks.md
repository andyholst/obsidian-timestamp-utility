# Tasks: `make loop-harness` — verbose, live-streamed terminal output

- [x] 1.1 In `scripts/run-loop-harness.sh`, change `run_stage` so `make <stage>` output is
      streamed to the terminal live AND still copied to `/tmp/loop_<stage>.log`. Uses `tail -f`
      on a log file (not `tee`) so the real container stdout is a file (nerdctl's forced `--tty`
      needs a console; a pipe makes it fail with "provided file is not a console") and the real
      `make` exit code is preserved (no pipe-through-tee masking of FAIL as PASS).
- [x] 1.2 Add a stage start banner: timestamp + a human-readable description of what the stage
      drives (e.g. "loop-build-app -> docker compose tools.yaml run app: npm run build").
- [x] 1.3 Add a per-stage elapsed-time + clear result line (PASS/FAIL/TIMEOUT) after the stage.
- [x] 1.4 Add a lightweight heartbeat (periodic elapsed update when the stage is quiet) so a
      long silent stage still shows it is alive, not hung.
- [x] 1.5 Preserve all existing behaviour: 7-stage order, per-stage `timeout` caps, surgical
      container teardown, non-zero exit on red gate.
- [x] 1.6 Run `make loop-harness` and confirm the terminal shows live stage output + progress
      (observe a quick stage like loop-build-app printing its real output, and a long stage
      showing a heartbeat). All 7 gates still green. No push.
- [x] 1.7 `openspec validate loop-harness-verbose-output`; then
      `make phase7-archive CHANGE=loop-harness-verbose-output`.
