# lint-trailing-whitespace Specification

## ADDED Requirements

### Requirement: Strip trailing whitespace from staged text files on commit
The pre-commit hook MUST, for every staged text file, remove trailing whitespace (spaces and tabs
at the end of each line) and re-stage the cleaned content so that the committed blob contains no
trailing whitespace. The hook MUST auto-fix the index and MUST NOT reject the commit.

#### Scenario: A staged file contains trailing whitespace
- **WHEN** a developer stages a text file that has one or more lines ending in trailing whitespace
  and runs `git commit`
- **THEN** the committed version of that file contains no trailing whitespace on any line, the
  non-whitespace content is byte-identical to what was staged, and the commit succeeds.

#### Scenario: A staged file is already clean
- **WHEN** a developer stages a text file that already has no trailing whitespace and runs
  `git commit`
- **THEN** the hook makes no changes to the file or index, and the commit succeeds unchanged.

#### Scenario: Binary or non-text staged files are ignored
- **WHEN** the staged set includes a binary file (e.g. an image) or a deleted/renamed file
- **THEN** the hook skips those entries, operates only on text files, and does not error.

### Requirement: Install the pre-commit hook via the existing hook installer
`make install-git-hooks` MUST install `git-hooks/pre-commit` into `.git/hooks/pre-commit` (marked
executable) in addition to the existing `commit-msg` hook, so a single command wires both.

#### Scenario: Running the installer wires both hooks
- **WHEN** a developer runs `make install-git-hooks`
- **THEN** both `.git/hooks/commit-msg` and `.git/hooks/pre-commit` exist, are executable, and the
  `pre-commit` hook contains the trailing-whitespace stripping logic.

### Requirement: The hook must not interfere with the agentic loop
The pre-commit hook MUST only act during a real `git commit`. Because the agentic loop never
commits (B4/B14), the hook MUST NOT execute or interfere during `make loop-harness`,
`make run-agentics`, `make build-app`, or `make test-app`.

#### Scenario: Loop verification runs with the hook installed
- **WHEN** `git-hooks/pre-commit` is installed and `make loop-harness` (or its stages) runs
- **THEN** the pre-commit hook does not run (no `git commit` is performed by the loop) and all loop
  gates pass exactly as they would without the hook present.
