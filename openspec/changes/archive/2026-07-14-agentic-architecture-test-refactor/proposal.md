## Why

The agentic Python codebase (`agents/agentics/src`, **51 modules**) is the engine that
generates the TS code + TS tests and self-corrects against `build-app`/`test-app`. To be
**harness-engineered / loop-engineered** reliably (generate correct TS, self-correct, never
omit existing logic), its architecture and test suite must be **solid and trustworthy**:

1. **Dead code / dead tests drag the loop down.** 51 modules and 67 tests exist, but a
   refactor pass is needed to confirm each module is actually wired into the workflow and
   each test targets live logic (not a deleted/mocked-out module). Dead units make the loop
   slow and hide real regressions.
2. **Test coverage must be good and honest.** The user requires that after refactor the
   *existing* tests still work, coverage stays high, and dead tests are removed. Unit tests
   must test real logic (mock only GitHub/Ollama/network/FS); integration/e2e must make real
   calls. This is the same rule as `agentic-tests-real-logic`.
3. **Architecture assessment is the prerequisite.** Before changing anything we must review
   whether the orchestration (composable_workflows → fetch_issue → ticket_clarity →
   implementation_planner → code_generator → test_generator → integrator →
   pre/post_test_runner → error_recovery) is sound enough to be loop-engineered, and fix
   weak points (e.g. the integrator currently *replaces* `main.ts` instead of *merging*,
   which causes omission).

## What Changes

- **Architecture review** (`design.md`): document the agent graph, identify dead/orphan
  modules, and confirm whether it is loop-ready. Flag the integrator merge vs replace bug.
- **Dead code removal**: remove modules that are never imported by the workflow/app entry
  (`python -m prod.agentics`) after confirming no live reference (keep a short allowlist).
- **Dead test removal**: delete unit/integration tests that target removed modules or assert
  on stubbed-out behaviour; keep coverage for live modules.
- **Coverage retention**: ensure each live module touched by the TS-generation path has a
  real unit test (real logic, external calls mocked) and the e2e path has a real-call
  integration test.
- All changes keep the **existing passing tests working** — the refactor does not break the
  green suite; it trims the dead parts and strengthens live coverage.

## Capabilities

### New Capabilities
- `agentic-architecture-test-refactor`: The agentic Python architecture is assessed and
  confirmed loop-ready; dead modules and dead tests are removed; coverage is retained and
  good; existing live tests keep passing after the refactor.

### Modified Capabilities
- `agentic-tests-real-logic`: this change operationalizes its "real logic / real calls /
  remove dead tests" rule against the live module set (the refactor trims dead tests and
  keeps real ones).
- `agentic-self-correct-loop`: the integrator merge-vs-replace fix (no omission) is a
  prerequisite so the loop never drops existing TS logic.

## Impact

- `agents/agentics/src/*`: some modules removed (dead), others strengthened.
- `agents/agentics/tests/unit/*` + `tests/integration/*`: dead tests removed; live tests
  kept and passing.
- `design.md`: architecture assessment + loop-readiness verdict.
