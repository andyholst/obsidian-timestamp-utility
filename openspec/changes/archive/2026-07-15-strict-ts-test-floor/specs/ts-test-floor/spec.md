# ts-test-floor Specification

## ADDED Requirements

### Requirement: Track TS test/command surface against origin/main
The harness MUST record four metrics of the plugin's TypeScript test/command surface for BOTH
the `origin/main` baseline and the current branch, and FAIL the loop if the current branch's
metric is strictly lower than the baseline:
- `describe` block count in `src/__tests__/main.test.ts`
- leaf `it`/`test` count in `src/__tests__/main.test.ts`
- `jest` **collected** test total (number jest actually collects/runs)
- `addCommand(...)` count in `src/main.ts`

#### Scenario: baseline computed from origin/main
- **WHEN** the guard runs
- **THEN** it computes the four metrics from `origin/main` (falling back to `main` if
  `origin/main` is absent) so the floor is stable across runs.

#### Scenario: current branch computed locally
- **WHEN** the guard runs
- **THEN** it computes the same four metrics from the current working tree
  (`src/main.ts` + `src/__tests__/main.test.ts`) and the jest-collected total from the current
  project.

### Requirement: Fail when any metric drops below baseline
The guard MUST exit non-zero (FAIL) when ANY of the four current-branch metrics is strictly less
than the `origin/main` baseline. It MUST NOT auto-allow a shrink — a silent feature/test removal
is exactly the regression this guard exists to catch.

#### Scenario: uuid command + tests removed
- **WHEN** the current branch has removed a feature present on `origin/main`
  (e.g. the `uuidv7` command and its `describe` block / leaf tests are gone)
- **THEN** the `describe` count, the leaf `it`/`test` count, the jest-collected total, and/or the
  `addCommand` count drop below baseline, and the guard FAILS (non-zero), blocking `loop-harness`.

#### Scenario: counts equal or higher
- **WHEN** every current-branch metric is greater than or equal to the baseline
- **THEN** the guard passes (exit 0). Adding a feature (more `describe`/leaf/`addCommand`) is allowed.

### Requirement: Guard runs hermetic and read-only as a loop stage
The guard MUST run WITHOUT Ollama/GitHub, WITHOUT internet, and WITHOUT modifying the tree. It
only diffs against `origin/main` and runs `jest --listTests`/collection. It MUST be wired into
`make loop-harness` as stage `loop-ts-floor` (a new early gate) and into
`scripts/run-loop-harness.sh`, and it MUST fail the whole run (no silent green) when red.

#### Scenario: loop-ts-floor is a loop stage
- **WHEN** `make loop-harness` (or `scripts/run-loop-harness.sh`) runs
- **THEN** `loop-ts-floor` executes as an early hermetic stage and a non-zero result marks the
  loop run as FAILED.

#### Scenario: hermetic
- **WHEN** `make loop-ts-floor` runs
- **THEN** it completes with no network dependency (uses local `origin/main` ref + local `npx jest`),
  so it is green-runnable in CI without Ollama.
