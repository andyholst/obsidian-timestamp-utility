## ADDED Requirements

### Requirement: `make loop-harness` streams each stage's output to the terminal live
The loop-harness runner (`scripts/run-loop-harness.sh`, which `make loop-harness` delegates
to) MUST, for every stage it runs, stream that stage's `make <stage>` stdout+stderr to the
terminal in real time (not only to a log file), so the user can observe actual progression
(rollup build lines, jest/pytest output) as it happens.

#### Scenario: a stage runs and produces output
- **WHEN** `run_stage` executes `make <stage>` and that stage prints container/pytest/jest
  output
- **THEN** those lines appear on the terminal live (interleaved as they are produced), and a
  copy is also written to `/tmp/loop_<stage>.log` for later inspection.

#### Scenario: a stage finishes quickly
- **WHEN** a stage (e.g. `loop-build-app`) completes in a few seconds
- **THEN** its real output (what the container ran) is still shown on the terminal before the
  `-> PASS` line, so the user sees WHAT executed rather than just a pass marker.

#### Scenario: a stage is silent for a while
- **WHEN** a stage produces no output for an extended period (e.g. a long `loop-integration`
  run)
- **THEN** the runner prints a start banner with a timestamp and the stage's human-readable
  description / service, plus a periodic heartbeat (e.g. a dot or elapsed-time update), so the
  user can distinguish "still working" from "hung".

#### Scenario: stage result is reported clearly
- **WHEN** a stage ends (pass / fail / timeout)
- **THEN** the runner prints a single clear result line (PASS / FAIL / TIMEOUT) with the
  stage's elapsed wall-clock time, and the final summary table still lists every stage's
  outcome.

### Requirement: verbose output must not change gate correctness
The live-streaming change MUST NOT alter the seven-stage order, the per-stage `timeout` caps,
the surgical container teardown, or the non-zero exit code on any red gate. It is an
observability change only.

#### Scenario: a stage still fails
- **WHEN** a stage's `make` exits non-zero under the new verbose runner
- **THEN** the result is still reported as FAIL (with the log path) and the overall run still
  exits non-zero exactly as before.
