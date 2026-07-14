# fetch-issue-agent-tests Specification

## Purpose
TBD - created by archiving change fix-fetch-issue-agent-tests. Update Purpose after archive.
## Requirements
### Requirement: No real CLI writes from unit tests
The `FetchIssueAgent` unit tests MUST NOT create real `openspec/changes/ticket<N>` directories on
disk during the run (the seed/load are mocked).

#### Scenario: no stray ticket change dirs after run
- **WHEN** the `test_fetch_issue_agent_unit.py` suite finishes
- **THEN** no `openspec/changes/ticket<N>` directory exists in the repo tree

