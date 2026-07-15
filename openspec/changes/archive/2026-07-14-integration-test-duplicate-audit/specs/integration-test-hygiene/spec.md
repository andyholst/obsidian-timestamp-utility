## ADDED Requirements

### Requirement: No strict-duplicate integration test files
The system MUST NOT contain two integration test files under
`agents/agentics/tests/integration/` that are strict duplicates of each other — i.e.
files that import the same `src.*` target modules AND assert the same set of behaviours.
When a duplicate is detected, the redundant file MUST be deleted, keeping the canonical
per-agent file.

#### Scenario: Duplicate detection and deletion preserves coverage
- **WHEN** the duplicate-audit detects two files with identical imported `src.*` modules and identical assertion targets
- **THEN** the agent deletes the redundant file and retains the canonical one, and `pytest tests/integration/ -m "integration and not e2e and not slow"` still passes with no loss of coverage

### Requirement: Distinct coverage is preserved
The system MUST retain every integration test file that exercises unique agentic
behaviour (error recovery, configuration, agent composer, npm tools, phase1–4
orchestration, cross-validation, immutable state, base agent) even if it overlaps
partially with another file. Only strict duplicates are removed.

#### Scenario: Partial overlap is not deleted
- **WHEN** two files share some imports or assertions but each covers at least one behaviour the other does not
- **THEN** both files are kept and the audit records the distinction
