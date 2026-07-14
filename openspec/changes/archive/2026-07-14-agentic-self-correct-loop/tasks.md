## 1. Scaffold the OpenSpec change
- [x] 1.1 Confirm `openspec/changes/agentic-self-correct-loop/` exists with `proposal.md`, `specs/agentic-self-correct-loop/spec.md`, `design.md`, and this `tasks.md`.
- [x] 1.2 Validate: `openspec validate agentic-self-correct-loop`.

## 2. Add lint gate to the Python loop
- [x] 2.1 In `post_test_runner_agent.py`, add `npm_run_tool lint` (or `npx eslint`/`prettier --check`) to the gate (combined with tsc in the lint gate).
- [x] 2.2 Non-zero lint exit MUST raise a recovery signal (`LintError`) so the loop re-enters `error_recovery`.
- [x] 2.3 Unit-test the lint gate (mock lint fail → `LintError` raised / recovery invoked).

## 3. Make the test gate require strict growth
- [x] 3.1 Change success condition in `post_test_runner_agent.py` from `tests_passed >= 0` to `tests_passed > existing_tests_passed` (also fixed the pre-existing `\\d` regex bug that made `tests_passed` always parse as 0).
- [x] 3.2 If not strictly greater, raise `TestRecoveryNeeded` with "test count did not grow".
- [x] 3.3 Unit-test: jest passes but count unchanged → recovery invoked (not success).

## 4. Omission guard in the Python loop
- [x] 4.1 In `exceptions.py` add `OmissionDetected` (and `LintError`, `TestRecoveryNeeded`).
- [x] 4.2 In `post_test_runner_agent.py`, after writing, compare `os.path.getsize` of `src/main.ts` and `src/__tests__/main.test.ts` vs the timestamped backup taken at run start.
- [x] 4.3 If a file is SMALLER, restore it and raise `OmissionDetected("generated <file> shrank; logic dropped")`.
- [x] 4.4 Unit-test: backup 1000 bytes, generated 200 bytes → restore + `OmissionDetected`.

## 5. Bounded self-correction wiring
- [x] 5.1 In `state.py` `State`, add `self_correct_success: bool` and `failing_gate: str`.
- [x] 5.2 In `composable_workflows.py`, wrap `post_test_runner → error_recovery → code_integrator` in an attempt counter (`MAX_SELF_CORRECT_ATTEMPTS = 5`).
- [x] 5.3 On `OmissionDetected` / `TestRecoveryNeeded` / `CompileError`, increment and re-run; after the bound, return `State` with `self_correct_success=False` and `failing_gate=<name>`.
- [x] 5.4 `output_result_agent.py` surfaces `self_correct_success=False` + `failing_gate` honestly (no "done" claim).

## 6. Feature / modal test generation
- [x] 6.1 In `test_generator_agent.py`, derive the feature name from the OpenSpec capability (e.g. `uuid-v7-modal`).
- [x] 6.2 Emit `src/__tests__/<feature>.test.ts` with UNIT tests (UUID v7 format / version / variant bits) AND MODAL tests (command registration, insertion at cursor, Notice when no active editor).
- [x] 6.3 Keep `src/__tests__/main.test.ts` updated; ensure total test count grows.

## 7. Align the other changes + verify
- [x] 7.1 Documentation: the loop is the `run-agentics` verification gate, documented in `AGENTS.md` B17 + `Makefile` `loop-harness` (the `docker-make-no-dagger` change dir is obsolete and was removed).
- [x] 7.2 The strict-growth + omission + feature-test gates are live in `post_test_runner_agent.py` and cited in `AGENTS.md` B11/B16; applied when `uuid-modal-agentic-generation` is processed.
- [x] 7.3 Verify gates: ran `make test-agents-unit-mock` on `main` (per user instruction: no worktree) → 519 passed, 6 failed (the 6 failures are pre-existing greetings/slim tests referencing change dirs that do not yet exist, out of scope). Lint gate, strict-growth gate, and omission guard are exercised by `test_post_test_runner_unit.py` (9 tests, all green).
- [x] 7.4 `openspec validate agentic-self-correct-loop` stays valid (all tasks ticked).

## 8. Document + decide
- [x] 8.1 `record-work` entry `agent-wiki/YYYY-MM-DD-agentic-self-correct-loop.md` with Verification Against Spec (loop-harness section of AGENTS.md covers the gates).
- [x] 8.2 Update `agent-wiki/index.md`.
- [x] 8.3 Archive: change is code-complete + verified; archive via `make phase7-archive CHANGE=agentic-self-correct-loop`.
