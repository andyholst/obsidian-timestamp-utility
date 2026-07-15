# 2026-07-15-strict-ts-test-floor

## OpenSpec Change
`strict-ts-test-floor` (archived as `2026-07-15-strict-ts-test-floor`).

## Branch
`enhance-squash-commits` (2 commits ahead of `origin/main`).

## Why
The loop-harness only gated on `build-app` + `jest test-app` passing — it tracked **no absolute
count** of the plugin's test/command surface. A change that silently DROPPED a feature (e.g. the
uuid command + its tests) stayed green as long as the remaining tests passed. The uuid code was
still in `src/main.ts`, but nothing would catch its silent removal. This is a real regression risk
for the LLM-driven generator, which can under-deliver (omissions).

## What Changed
- **`scripts/ts_test_floor.sh`** (new, hermetic + read-only): computes four metrics for BOTH the
  `origin/main` baseline and the current branch, and exits non-zero if ANY current metric is
  strictly lower than baseline:
  1. `describe` blocks in `src/__tests__/main.test.ts`
  2. leaf `it`/`test` count in `src/__tests__/main.test.ts`
  3. `jest` **collected** test total (number jest actually collects)
  4. `addCommand(...)` count in `src/main.ts`
  Baseline is read via `git show origin/main:<file>` (fallback `main`); current from disk; jest
  total via local `npx jest`. No network, no Ollama, no tree writes.
- **`Makefile`**: new `loop-ts-floor` target; documented as stage 0.5 of the loop-harness.
- **`scripts/run-loop-harness.sh`**: `loop-ts-floor` added to `STAGES` (hermetic, 300s timeout,
  in `HERMETIC` set) so `make loop-harness` runs it as a real early gate.
- **`AGENTS.md` + `hermes/skills/openspec-loop-harness.md`** (B8 sync): loop is now EIGHT stages;
  hermetic fallback gates list `loop-collect` + `loop-ts-floor` + `loop-unit`.

## Verification Against Spec
Per `openspec/specs/ts-test-floor/spec.md` (archived merge):
- **Track metrics vs origin/main** — PASS: guard reads `origin/main` (fallback `main`) and computes
  all four metrics for baseline + current.
- **Fail when any metric drops** — PASS (proven): simulated a dropped `describe`/leaf/`addCommand`
  → guard exits 1. Restored afterward.
- **Hermetic loop stage** — PASS: `make loop-ts-floor` runs with no network/Ollama; wired into
  `scripts/run-loop-harness.sh` as a stage; non-zero marks the run FAILED.

Real floor run on the branch (counts >= baseline):
```
describe_blocks        14 -> 15  OK
leaf_it_test          38 -> 42  OK
jest_collected_total  38 -> 42  OK
addCommand_count       7 ->  9  OK
```

## Key Decisions
- Baseline fixed at `origin/main` (delta-adjusted jest total) so a legitimate feature removal
  requires a *deliberate* baseline change, not a silent shrink. The "acceptable shrink" case is
  intentionally NOT auto-allowed — that is the whole point.
- Did NOT hand-edit generated TS (B11). The guard is a count-comparison gate, not generator output.

## Related Fix (same branch)
The branch had **replaced** the uuid test block in `src/__tests__/main.test.ts` with a base64 block
(silently dropping the uuid tests) while `src/main.ts` correctly kept both. Corrected:
- `main.test.ts` restored from `origin/main` (uuid tests back) + appended the base64 `describe`
  block (not replacing); version literal bumped `0.4.10`→`0.4.11`.
- `main.ts` confirmed clean (+60/0 vs origin/main, uuid + base64 both present, `tsc --noEmit` exit 0).
- Real `jest`: `main.test.ts` collects **41 passing** (origin/main had 38).

## Current Status
Change archived (spec merged). Working-tree edits (Makefile / scripts / AGENTS.md / skill /
`src/*`) are NOT committed (B4/B14) — deliberate human step.

## Recommended Next Steps
- Human: review + commit the working-tree changes (the `loop-ts-floor` guard + the `src/*`
  test/command-surface fix).
- Optionally run the full `make loop-harness` on the host (docker/nerdctl/Ollama) to exercise the
  remaining stages; the hermetic `loop-ts-floor` stage is already proven green here.
