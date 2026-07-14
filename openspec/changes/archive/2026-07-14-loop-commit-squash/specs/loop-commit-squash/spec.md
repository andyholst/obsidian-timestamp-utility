## ADDED Requirements

### Requirement: `make commit` produces one thorough, file-grounded Angular commit vs `main`
The `commit` Make target MUST, when invoked on the current branch:
- Compute the diff base as `origin/main` (fallback `main`), NOT the loose
  upstream tracking branch.
- Pass Hermes (project-manager profile) the **list of changed files** and a
  **diff-stat** versus `main`, and instruct it to write a Conventional/Angular
  commit message whose body **describes the actual behavioural changes in
  those files** (what the code now does and why), not the commit tooling.
- Create exactly **one** commit on the current branch that squashes every
  commit currently ahead of `main` (via `git reset --soft <main>` then
  `git commit -m "<hermes-message>"`).
- **Never push** (B14). If Hermes returns no message, run
  `git reset --quit <main>` to restore the pre-squash state and abort, leaving
  no empty or partial commit.

#### Scenario: branch has many WIP commits ahead of main
- **WHEN** `make commit` runs and the branch is N commits ahead of `main`
- **THEN** it collapses all N into a single commit whose message is drafted
  by Hermes from the changed files vs `main`, and the branch ends exactly
  one commit ahead of `main` (working tree clean, nothing pushed).

#### Scenario: Hermes returns an empty message
- **WHEN** the Hermes call yields no usable message
- **THEN** the target aborts with a clear error and restores the pre-squash
  state (`git reset --quit <main>`), so no empty/partial commit remains and
  the original WIP commits are intact.

#### Scenario: nothing differs from main
- **WHEN** the branch has no commits ahead of `main` and a clean tree
- **THEN** the target reports "nothing to squash/commit" and exits 0 without
  touching history.
