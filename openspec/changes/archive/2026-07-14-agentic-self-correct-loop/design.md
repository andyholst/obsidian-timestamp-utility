# Design — agentic-self-correct-loop

## Current state (what exists today)
- `PostTestRunnerAgent.process` runs `npm install` → `typescript_typecheck_tool` (tsc --noEmit)
  → `npm_run_tool test` (jest), parses `Tests: X passed Y total`, and records
  `tests_improvement = tests_passed − existing_tests_passed`.
- It already backs up `src/main.ts`, `src/__tests__/main.test.ts`, `package.json`,
  `tsconfig.json` into `backups/<timestamp>/` (the Python-side backup).
- `make run-agentics` ALSO does a timestamped bash backup + omission guard (size shrink →
  restore). Two layers of safety already exist; this change makes the **Python loop** own
  the hard gates and the omission guard, and adds lint + test-growth + feature test files.

## Change plan
1. **Add lint to the gate.** In `post_test_runner_agent.py`, before/after tsc, run
   `npm_run_tool lint` (or `npx eslint`). Non-zero → raise `TestRecoveryNeeded`
   (or a new `LintError`) so the loop re-enters `error_recovery`.
2. **Make test growth strict.** Change the success condition from
   `tests_passed >= 0` / `tests_improvement >= 0` to
   `tests_passed > existing_tests_passed` (strict). If not, raise `TestRecoveryNeeded`
   with the message "test count did not grow".
3. **Omission guard in Python.** After `code_integrator` writes the files, compare
   `os.path.getsize(src/main.ts)` and `src/__tests__/main.test.ts` against the
   timestamped backup taken at run start. If smaller → restore the backup via
   `write_file_tool`, and raise a NEW `OmissionDetected` exception carrying
   "generated <file> shrank (before -> after); logic was dropped".
4. **Bounded loop.** In `composable_workflows.py`, wrap
   `post_test_runner → error_recovery → code_integrator` in an attempt counter
   (default `MAX_SELF_CORRECT_ATTEMPTS = 5`). On `OmissionDetected` /
   `TestRecoveryNeeded` / `CompileError`, increment and re-run; after the bound,
   return a failure `State` with `self_correct_success=False` and the failing gate name.
5. **Feature/modal test files.** In `test_generator_agent.py`, derive the feature name
   from the OpenSpec capability (e.g. `uuid-v7-modal`) and emit
   `src/__tests__/<feature>.test.ts` with unit tests (format/version/variant bits) AND
   modal-command tests (command registration, insertion at cursor, Notice when no
   active editor). Keep `main.test.ts` updated too.
6. **State/exceptions.** Add `OmissionDetected` to `exceptions.py`; add
   `self_correct_success: bool` and `failing_gate: str` to `state.py` `State`.
7. **Honest reporting.** `agentics.py` / `output_result_agent.py` must surface
   `self_correct_success=False` + `failing_gate` rather than claiming done.

## Interaction with other changes
- `docker-make-no-dagger` owns `make run-agentics` (bash backup + guard). This change
  aligns the Python loop with it (defense in depth).
- `uuid-modal-agentic-generation` is the first consumer: it will benefit from the
  strict-growth + omission + feature-test gates automatically.
