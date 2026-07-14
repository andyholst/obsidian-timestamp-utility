# Capability: python-agentic-slim-refactor

Reduce the agentic Python codebase so it matches harness / loop-engineering / OpenSpec engineering
(one generation path, no unwired modules, no redundant orchestration) while preserving behaviour.

## ADDED Requirements

### Requirement: Classify every module against the harness model
The change MUST document an analysis that classifies each `agents/agentics/src` module as
aligned / duplicated-parallel / unwired-dead, with the evidence (import graph, live-graph usage).

#### Scenario: Analysis is recorded
- **WHEN** the refactor begins
- **THEN** a module-by-module classification exists in `design.md` / `tasks.md` with evidence.

### Requirement: Remove unwired dead-weight modules
Modules not imported by the live graph (`agentics.py`, `composable_workflows.py`, `workflows.py`)
and not covered by a required test MUST be removable without breaking imports or the e2e.

#### Scenario: Removal leaves imports intact
- **WHEN** an unwired module is removed
- **THEN** no remaining module fails to import and `ticket20`/`ticket22` e2e still pass.

### Requirement: Consolidate parallel generation/validation stacks
The harness needs ONE generation path (one generator + `CodeIntegratorAgent` deterministic floor).
Parallel/duplicate generator and validator classes MUST be consolidated or removed.

#### Scenario: Single generation path
- **WHEN** generation runs
- **THEN** exactly one generator implementation participates, and the deterministic floor remains
  the sole writer of `src/main.ts` / `src/__tests__/main.test.ts`.

### Requirement: Eliminate redundant orchestration indirection
`composable_workflows.py` duplicate imports and redundant state adapters MUST be cleaned, and the
orchestration MUST read as the bounded fetch → (seed local OpenSpec) → generate → integrate →
test self-correct loop the harness describes.

#### Scenario: Clean orchestration
- **WHEN** the orchestration module is read
- **THEN** it has no duplicate imports and no unnecessary adapter layers beyond what the loop needs.

### Requirement: Behaviour is preserved (e2e proof of concept)
After slimming, the pipeline MUST produce the same generated TS and the `ticket20`/`ticket22` e2e
tests MUST remain green.

#### Scenario: e2e stays green
- **WHEN** the refactor is complete
- **THEN** `test_ticket20_e2e_integration.py` and `test_ticket22_e2e_integration.py` pass, and all
  previously-passing unit/integration tests still pass.

## ADDED Acceptance Criteria

- `openspec validate python-agentic-slim-refactor` passes.
- `python -c "import src.agentics"` succeeds after every removal/consolidation step.
- Unit + integration suites that passed before still pass (run the hermetic integrator + loader
  files; reserve the broad `make verify-agentics-after-run` for the final gate).
- `test_ticket20_e2e_integration.py` + `test_ticket22_e2e_integration.py` pass (the proof of concept).
- New unit/integration tests are added as findings accumulate so the slimmed behaviour is covered.
