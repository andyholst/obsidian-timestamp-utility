## ADDED Requirements

### Requirement: Review-approved loop-final finalisation

The system MUST provide a `make loop-final` target that finalises an open, human-approved PR by
squashing to one typed commit, regenerating the changelog from that commit, and force-pushing the
feature branch — permitted ONLY after explicit human approval and a fresh green loop-harness.

#### Scenario: Human approval unlocks squash + force-push

- **WHEN** a human explicitly approves an open PR (an approval phrase such as "PR looks great",
  "looks good", or "approved to finalize") and the agent runs `make loop-final BRANCH=<feat/...>
  APPROVED=1`
- **THEN** the target MUST run a fresh `make loop-harness`, require it GREEN, then run
  `squash-commits`, regenerate the CHANGELOG from the squash commit, and
  `git push --force-with-lease` the feature branch (never `main`).

#### Scenario: Fresh loop-harness must be green before any rewrite

- **WHEN** `make loop-final` is invoked
- **THEN** it MUST run `make loop-harness` FIRST and MUST abort (non-zero, no squash, no
  force-push) if any stage is not green — history is never rewritten on a red gate.

#### Scenario: No approval means no squash or force-push

- **WHEN** `make loop-final` is invoked WITHOUT the human approval flag (`APPROVED` unset)
- **THEN** it MUST refuse (fail closed) and perform no squash and no force-push, preserving the
  default B28a/B30b protection of an open PR.

#### Scenario: Force is scoped and revert stays forbidden

- **WHEN** `make loop-final` force-pushes
- **THEN** it MUST use `--force-with-lease` against the feature branch ONLY, MUST refuse to target
  `main`/`origin/main`, and MUST NOT run `git revert` (B30a remains absolute).

### Requirement: B8 doc-sync reflects loop-final behaviour

The system MUST keep all B8 sync docs describing the new `loop-final` behaviour identically and
MUST keep `make check-docs-sync` green with the updated behaviour range.

#### Scenario: check-docs-sync passes with the new behaviour

- **WHEN** `make check-docs-sync` runs after this change
- **THEN** it MUST pass, with AGENTS.md, the skill mirror, the docs reference, the Makefile, and
  `scripts/run-loop-harness.sh` all agreeing on the behaviour range and stage order.
