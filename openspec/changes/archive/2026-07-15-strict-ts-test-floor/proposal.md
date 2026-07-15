# Proposal: Strict TS Test Floor

## Why
The loop-harness currently gates on `build-app` + `jest test-app` passing, but it tracks **no absolute count** of the plugin's test/command surface. If a change (an agentic regeneration, a refactor, or a manual edit) DROPS a feature — e.g. the uuid command + its tests — the harness stays green as long as the *remaining* tests still pass. The `uuid` code is still in `src/main.ts` today, but nothing would catch its silent removal: there is no baseline to compare against.

This is a real regression risk: the LLM-driven generator can under-deliver (omissions), and a trimmed `main.test.ts` that still passes is indistinguishable from a correct one without a count floor.

## What Changes
Add a **strict TS test floor** guard that the loop-harness runs as an early, hermetic gate:

1. A script (`scripts/ts_test_floor.sh`) that, against `origin/main`, computes four metrics for the plugin's TypeScript:
   - `describe` blocks in `src/__tests__/main.test.ts`
   - leaf `it`/`test` count in `src/__tests__/main.test.ts`
   - `jest`**collected** test total (the number jest actually runs — robust against duplicates/empty suites)
   - `addCommand(...)` count in `src/main.ts` (the command surface)
2. It computes the **same four metrics for the current branch** and **FAILS (non-zero)** if ANY current metric is **strictly less** than the `origin/main` baseline.
3. Wire it into `make loop-harness` as a new stage `loop-ts-floor` (runs hermetic, before/with `loop-collect`) and into `scripts/run-loop-harness.sh`.

The baseline is `origin/main`, so the floor is stable: removing a feature legitimately requires *also* lowering the recorded baseline (an explicit, reviewed decision), not a silent shrink. The "acceptable shrink" case is intentionally NOT auto-allowed — that is the whole point: the harness must be more strict.

## Capabilities
- `ts-test-floor` (new): the count-tracking guard that fails the loop when the current branch's TS test/command surface drops below `origin/main`.

## Impact
- Loop-harness gains stage 0.5 (loop-ts-floor) — `make loop-harness` must show it GREEN.
- No git commit/push (B4/B14). The guard is read-only (diffs against `origin/main`, runs jest `--listTests`/`--collectOnly`).
- Must NOT regress: deterministic floor (B11), B9 perms, e2e gates (B1/B3), false-skip rule (B17).
- Explicitly out of scope: raising the floor when a feature is added is fine (current > baseline passes). Lowering it must be a deliberate change to the baseline (e.g. an OpenSpec change that intentionally removes the uuid feature and updates the recorded baseline).
