# implementation-planner-hermetic-tests Specification

## Purpose
TBD - created by archiving change fix-fetch-issue-agent-tests. Update Purpose after archive.
## Requirements
### Requirement: ImplementationPlannerAgent unit tests are hermetic
The `ImplementationPlannerAgent` unit tests MUST inject a mocked LLM (`.invoke()` returns a JSON
planning response) rather than the live `llm_reasoning` client, so the suite is deterministic and
does not depend on a live Ollama model.

#### Scenario: planner merges mocked LLM response into enhanced ticket
- **WHEN** `ImplementationPlannerAgent` processes a refined ticket with a mocked LLM returning a
  JSON plan
- **THEN** `state["refined_ticket"]` contains `implementation_steps`, `npm_packages`, and
  `manual_implementation_notes`, and the original title/description/requirements/acceptance_criteria
  are preserved

