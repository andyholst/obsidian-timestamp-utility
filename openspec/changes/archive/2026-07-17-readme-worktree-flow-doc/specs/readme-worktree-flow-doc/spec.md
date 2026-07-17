## ADDED Requirements

### Requirement: README documents the per-change worktree flow
The README MUST include a section explaining that every OpenSpec change is implemented and verified
inside an isolated **local** git worktree sandbox (`worktrees/<name>`, branch `wt/<name>`), and that
the parent working tree is never modified by the change's work.

#### Scenario: reader wants to know how a change is isolated
- **WHEN** a reader opens README.md looking for how changes are built
- **THEN** they find a section stating each change runs in a local `wt/<name>` worktree sandbox and the parent working tree is untouched

### Requirement: README documents the delivery / branch-governance rule
The README MUST state that a named remote PR branch (`feat/<name>`) is created ONLY on an explicit
human "make the PR" instruction (governance rule B27), and that multiple changes can deliver in
parallel to distinct PR branches.

#### Scenario: reader wants to know when a remote branch/PR is created
- **WHEN** a reader opens README.md looking for when a branch/PR is pushed
- **THEN** they find a statement that the agent does NOT auto-create a remote branch for every change; a `feat/<name>` PR branch is made only when a human explicitly requests delivery, and parallel delivery to distinct branches is supported

### Requirement: README links to the full harness reference
The README section MUST link to `docs/openspec-engineering-loop-harness.md` for the full loop/flow machinery.

#### Scenario: reader wants the deep reference
- **WHEN** a reader finishes the README summary and wants detail
- **THEN** the README links to `docs/openspec-engineering-loop-harness.md`
