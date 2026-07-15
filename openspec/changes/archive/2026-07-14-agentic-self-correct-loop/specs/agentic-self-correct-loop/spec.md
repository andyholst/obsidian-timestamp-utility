# Capability: agentic-self-correct-loop

The Python agentic pipeline MUST self-correct generated TypeScript until it is correct and complete (no omissions, tests grow).

## ADDED Requirements

### Requirement: Lint gate in the loop
The agentic loop MUST run a lint step (`npm run lint` or `npx eslint`/`prettier --check`) on the generated TypeScript and MUST NOT consider the run successful unless lint exits 0.

#### Scenario: Lint failure triggers re-generation
- **WHEN** the lint step exits non-zero on the generated `src/main.ts` / `src/__tests__/main.test.ts`
- **THEN** the loop re-enters `error_recovery` with the lint errors and re-generates, and does not report success.

### Requirement: TypeScript build gate
The agentic loop MUST run `tsc --noEmit` (or `npm run build`) on the generated TypeScript and MUST NOT consider the run successful unless the type-check exits 0.

#### Scenario: Type error triggers re-generation
- **WHEN** `tsc --noEmit` reports one or more `error TS` on the generated files
- **THEN** the loop re-enters `error_recovery` with the parsed errors and re-generates, and does not report success.

### Requirement: Test pass and growth gate
The agentic loop MUST run `npm test` (jest) and MUST NOT consider the run successful unless jest exits 0 AND `tests_passed > existing_tests_passed` (strict growth over the pre-existing suite).

#### Scenario: Tests pass but count did not grow
- **WHEN** jest exits 0 but `tests_passed` is not strictly greater than the pre-integration `tests_passed`
- **THEN** the loop treats it as a failure and re-generates the missing/insufficient tests.

#### Scenario: Tests fail
- **WHEN** jest exits non-zero
- **THEN** the loop re-enters `error_recovery` with the failing test output and re-generates, up to a bounded attempt count.

### Requirement: Omission guard
After writing `src/main.ts` and `src/__tests__/main.test.ts`, the loop MUST compare each file's byte size against its timestamped backup; if a generated file is SMALLER than the backup, the loop MUST restore the backup and re-enter `error_recovery` with the explicit signal that logic was dropped.

#### Scenario: Generated file shrank
- **WHEN** the generated `src/main.ts` (or `main.test.ts`) has fewer bytes than its timestamped backup
### Requirement: All generated TS features are Obsidian Modals registered as commands
**Every** generated TS feature MUST be implemented as an `obsidian.Modal` subclass and MUST
be registered as an Obsidian command in `src/main.ts` via `this.addCommand({ id, name,
callback: () => new <Feature>Modal(this.app).open() })`, so the feature is reachable from the
command palette. This applies to ALL generated TS code (e.g. the UUID v7 modal, the timestamp
modal, and any future feature) — never emit a generated feature as a bare function/utility
without a Modal + command registration.

#### Scenario: Generated feature is a Modal wired as a command
- **WHEN** generation completes for any TS feature
- **THEN** `src/main.ts` imports the `<Feature>Modal` class, registers it with `addCommand`
  (callback opens the modal), and the modal is an `obsidian.Modal` subclass; existing
  `main.ts` logic is preserved (no omission).

### Requirement: Feature and modal test generation
The pipeline MUST emit a dedicated test file `src/__tests__/<feature>.test.ts` (for example
`uuid-v7-modal.test.ts`) containing unit tests AND modal-command tests (command registration,
modal open, cursor insertion, no-active-editor Notice), in addition to updating
`src/__tests__/main.test.ts`.

#### Scenario: Feature test file exists with modal tests
- **WHEN** generation completes for a modal command feature
- **THEN** `src/__tests__/<feature>.test.ts` exists, is non-empty, and asserts modal command
  behaviour (registration, modal open, insertion at cursor, Notice when no editor).

### Requirement: Integration into main.ts and main.test.ts
The pipeline MUST integrate the generated modal code and its tests into the EXISTING plugin
files, not leave them as orphan/unreferenced code:
- The modal command MUST be **imported and registered** in `src/main.ts` (wired through the
  Obsidian command API / plugin entry point, e.g. `addCommand` with id `insert-uuid-v7`),
  so the feature is actually reachable from the command palette.
- The modal tests MUST be **appended into** `src/__tests__/main.test.ts` (in addition to the
  separate `<feature>.test.ts`), so both the dedicated and the main suite exercise the modal.

#### Scenario: Modal command wired into main.ts
- **WHEN** generation completes for a modal command feature
- **THEN** `src/main.ts` imports the UUID v7 function and registers the command (the command is present in the plugin's registered commands), and existing `main.ts` logic is preserved (no omission).

#### Scenario: Modal tests present in both suites
- **WHEN** generation completes for a modal command feature
- **THEN** `src/__tests__/main.test.ts` contains modal-command tests AND `src/__tests__/<feature>.test.ts` exists, so the modal is covered by the main suite and the dedicated unit/modal suite.

### Requirement: Bounded self-correction
The loop MUST re-enter `error_recovery → code_generator → code_integrator` on any gate failure, up to a bounded number of attempts (default 5), and MUST report honestly (with the failing gate) if the bound is reached without success.

#### Scenario: Bound reached without success
- **WHEN** the attempt bound is reached and at least one gate still fails
- **THEN** the pipeline returns a failure result naming the failing gate, and does not claim the change is done.

## ADDED Acceptance Criteria

- `npm run lint` passes on generated TS.
- `tsc --noEmit` (or `npm run build`) compiles generated TS with no error.
- `npm test` passes AND `tests_passed > existing_tests_passed`.
- No generated `main.ts`/`main.test.ts` is smaller than its timestamped backup (omission guard).
- `src/__tests__/<feature>.test.ts` exists with unit + modal tests.
- On gate failure the loop retries up to the bound and reports the failing gate if still failing.
