# Capability: agentic-architecture-test-refactor

The agentic Python architecture is assessed and confirmed loop-ready; dead modules and
dead tests are removed; coverage is retained and good; existing live tests keep passing
after the refactor.

## ADDED Requirements

### Requirement: Architecture assessed for loop-readiness
The agent graph (composable_workflows → fetch_issue → ticket_clarity →
implementation_planner → code_generator → test_generator → integrator →
pre/post_test_runner → error_recovery) MUST be documented in `design.md` with a verdict
on whether it is solid enough to be harness/loop-engineered for TS generation + self-correction.

#### Scenario: Architecture documented with verdict
- **WHEN** the refactor design is written
- **THEN** `design.md` lists every live module, its role in the graph, and an explicit
  loop-readiness verdict (ready / needs-fix) plus the integrator merge-vs-replace finding.

### Requirement: Dead modules removed with proof
A module MUST be removed only if no live code reference (import) exists in the workflow
entry (`python -m prod.agentics`) or other live modules (after an import-graph scan), or
it is on an explicit keep-allowlist.

#### Scenario: Removal is reference-checked
- **WHEN** a module is proposed for removal
- **THEN** a grep/import-scan shows zero live references (or it is allowlisted) before deletion.

### Requirement: Dead tests removed
A test file/function MUST be removed when it targets a removed module, or only asserts on
stubbed/mocked-out behaviour of a module that no longer exists, or duplicates another live
test.

#### Scenario: Dead test removed
- **WHEN** a test references a removed module or asserts only on mocked-out dead logic
- **THEN** it is deleted and `make test-agents-unit` + `make test-agents-integration` still pass.

### Requirement: Coverage retained and good
After refactor, every live module on the TS-generation path MUST still be covered by at
least one real unit test (real logic; external GitHub/Ollama/network/FS mocked) and the
e2e path MUST still have a real-call integration test. Overall unit coverage MUST NOT drop
below the pre-refactor baseline.

#### Scenario: Coverage baseline held
- **WHEN** the refactor completes
- **THEN** `pytest --cov` (unit) is at or above the pre-refactor baseline and the generation
  e2e still makes a real Ollama call.

### Requirement: Existing live tests keep passing
The refactor MUST NOT break any test that targets a live module. All surviving tests MUST pass.

#### Scenario: Green suite preserved
- **WHEN** `make test-agents` runs after refactor
- **THEN** it passes with no regressions in live-module tests.

## ADDED Acceptance Criteria

- `design.md` contains the architecture graph + loop-readiness verdict + integrator finding.
- No live module imports a deleted module (import-graph scan clean).
- Dead tests removed; `make test-agents-unit` + `make test-agents-integration` pass.
- Unit coverage ≥ pre-refactor baseline.
- `make test-agents-real` (real logic / real calls) passes.
