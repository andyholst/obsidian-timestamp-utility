## Why

The current `uuid-modal-agentic-generation` proposal assumes the Python agentic pipeline
self-corrects, but the **loop is not strong enough** to guarantee correctness:

- `PostTestRunnerAgent` runs `npm install` → `tsc --noEmit` → `npm test` and reports
  `tests_improvement`, but there is **no hard gate** that requires tests to PASS and the
  test count to strictly GROW before the run is considered successful.
- There is **no omission guard**: if the generated `src/main.ts` or
  `src/__tests__/main.test.ts` comes out SMALLER than the prior version (the pipeline
  dropped existing logic), nothing detects or restores it.
- There is **no lint step** in the loop, and **no modal-specific / feature-specific test
  files** are mandated — only `main.ts` + `main.test.ts` are regenerated.
- The `docker-make-no-dagger` proposal has **zero** self-correction language, even though
  it owns the `make run-agentics` harness that runs this loop.

We need a single change that makes **harness engineering + loop engineering** explicitly require
the agentic code to self-correct `main.ts` / `main.test.ts` until: lint passes, `tsc`
builds, jest passes, **test count is strictly greater than before**, the files were not
shrunk (omission guard), and feature/modal/unit tests exist.

## What Changes

- Strengthen `agents/agentics/src/post_test_runner_agent.py` (and the
  `error_recovery → code_integrator` wiring in `composable_workflows.py`) so the loop is a
  **hard gate**:
  1. `npm run lint` (or `npx eslint`/`prettier --check`) MUST exit 0.
  2. `tsc --noEmit` (`npm run build`/`validate-ts`) MUST exit 0.
  3. `npm test` (jest) MUST exit 0 AND `tests_passed > existing_tests_passed`
     (strict growth), not just `>=`.
  4. **Omission guard**: after writing, compare byte size of `src/main.ts` and
     `src/__tests__/main.test.ts` vs their timestamped backup. If a generated file is
     SMALLER, treat it as a failure → restore the backup and feed "you dropped logic" back
     into `error_recovery`.
  5. Feature/modal/unit test generation: the pipeline MUST also emit
     `src/__tests__/<feature>.test.ts` (e.g. `uuid-v7-modal.test.ts`) with modal
     command tests, plus the unit tests, so total test count grows.
- Add an `OMISSION` failure signal to `state.py`/`exceptions.py` so the loop re-runs
  `code_generator → code_integrator` with that context.
- `make run-agentics` already backs up `main.ts`/`main.test.ts` (timestamped) and runs the
  omission guard in bash; this change makes the **Python** loop own the same guarantee
  (defense in depth).
- Update `docker-make-no-dagger` `tasks.md` to reference this loop as the verification
  gate for `run-agentics`.

## Capabilities

### New Capabilities
- `agentic-self-correct-loop`: The agentic pipeline MUST iterate (generate → lint → build
  → test → omit-guard) until the TS code + TS tests are correct and **complete** (no dropped
  logic, test count grows). Failure on any gate re-enters `error_recovery` with the specific
  failure, up to a bounded number of attempts, then reports honestly.

### Modified Capabilities
- `uuid-v7-modal` (from `uuid-modal-agentic-generation`): the generated `main.test.ts`
  MUST include modal-command tests, and a dedicated `uuid-v7-modal.test.ts` MUST exist
  with unit + modal tests; the loop MUST verify test count growth.

## Impact

- Python agentic code: `post_test_runner_agent.py`, `error_recovery_agent.py`,
  `code_integrator_agent.py`, `composable_workflows.py`, `state.py`, `exceptions.py`,
  `test_generator_agent.py`, `code_generator_agent.py`.
- Makefile: `run-agentics` already does timestamp backup + bash omission guard; this change
  aligns the Python loop with it.
- The `docker-make-no-dagger` change's verification wording gains explicit self-correction.
