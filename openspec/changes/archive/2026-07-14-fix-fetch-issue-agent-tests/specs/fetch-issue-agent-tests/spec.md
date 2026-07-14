## ADDED Requirements
### Requirement: FetchIssueAgent seed-then-load bridge is unit-covered
The system MUST have deterministic unit tests for `FetchIssueAgent` that exercise the B15
seed-then-generate bridge (fetch GitHub issue → `create_change_from_issue` → `load_change`)
without performing real CLI writes.

#### Scenario: valid GitHub issue is fetched and re-pointed to local change
- **WHEN** `FetchIssueAgent` processes a valid GitHub issue URL with `create_change_from_issue`
  and `load_change` mocked
- **THEN** `state["ticket_content"]` equals the seeded local change's content and `state["url"]`
  is re-pointed to `openspec:<change>`

#### Scenario: closed GitHub issue is fetched and re-pointed to local change
- **WHEN** `FetchIssueAgent` processes a closed GitHub issue with the bridge mocked
- **THEN** `state["ticket_content"]` equals the seeded local change's content and `state["url"]`
  is re-pointed to `openspec:<change>`

## ADDED Requirements
### Requirement: No real CLI writes from unit tests
The `FetchIssueAgent` unit tests MUST NOT create real `openspec/changes/ticket<N>` directories on
disk during the run (the seed/load are mocked).

#### Scenario: no stray ticket change dirs after run
- **WHEN** the `test_fetch_issue_agent_unit.py` suite finishes
- **THEN** no `openspec/changes/ticket<N>` directory exists in the repo tree
