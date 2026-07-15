# Capability: integrator-merge-refactor

The integrator merges generated TypeScript into the existing `main.ts` using a deterministic,
anchor-based algorithm that honors the OpenSpec spec contract exactly, preserves all existing
logic, tolerates corrupted LLM output, and produces tsc/rollup-clean output.

## ADDED Requirements

### Requirement: Anchor-based merge (no whole-file brace surgery)
The integrator MUST merge generated code into `main.ts` by anchoring on stable markers
(the imports block, the `onload()` method, the `export default class TimestampPlugin` closing
brace, and the end of file) rather than scanning the entire file for braces.

#### Scenario: Stable merge from anchors
- **WHEN** the integrator merges generated code into an existing `main.ts`
- **THEN** imports are appended after the import block, commands land inside `onload()`, the
  Modal is a top-level class at file end, and the generator method is inside `TimestampPlugin`,
  with no orphaned `export` token and no duplicate braces.

### Requirement: Spec contract wins
The integrator MUST honor the OpenSpec-mandated command id / name / Modal class exactly. Any
LLM-emitted command or Modal carrying the contract id/name MUST be stripped before the
authoritative injection, so exactly one spec-exact instance remains.

#### Scenario: Conflicting LLM command stripped
- **WHEN** the LLM emits a `this.addCommand({ id: '<contract-id>' ... })` or a `class <ContractModal>`
- **THEN** only the spec-exact command/Modal remains (count == 1) and existing non-contract
  commands are preserved.

### Requirement: Modal top-level, generator in-class
The generated Modal MUST be a top-level `class X extends obsidian.Modal` (appended at file end
if absent). The spec generator MUST be a method **inside** `TimestampPlugin` (appended before
the class closing brace if absent). Output MUST compile under tsc/rollup.

#### Scenario: Well-formed, compilable output
- **WHEN** assembly completes
- **THEN** `generateUuidV7` (or the spec generator) resolves as `this.generateX()` inside the
  plugin class, the Modal is top-level, and there is no orphaned `export` keyword.

### Requirement: No omission
The merge output MUST be at least as large as the existing content (existing logic is never
dropped). A smaller output is treated as a failure and restored from backup.

#### Scenario: Size preserved
- **WHEN** the merge runs on an existing `main.ts`
- **THEN** `len(merged) >= len(existing)`.

### Requirement: Escaped-newline tolerance
LLM output that contains literal `\n` / `\t` escape sequences MUST be normalised to real
newlines/tabs before merging so brace balancing and jest parsing stay correct.

#### Scenario: Corrupted LLM output normalised
- **WHEN** the LLM emits a block with literal `\n` escapes
- **THEN** the merge normalises it and still produces a single balanced, valid command/Modal.

## ADDED Acceptance Criteria
- A real unit test asserts: contract command count == 1, top-level Modal count == 1, generator
  method inside `TimestampPlugin`, no orphaned `export`, `len(merged) >= len(existing)`.
- `make test-agents-unit-mock` passes.
- `make build-app` + `make test-app` pass for the `uuid-modal-agentic-generation` change.
