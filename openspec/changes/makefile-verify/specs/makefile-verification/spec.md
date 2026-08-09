## ADDED Requirements
### Requirement: Every make target exits cleanly or produces expected output
The Makefile targets MUST each execute without unexpected errors when run from the project root.

#### Scenario: Simple targets (no containers)
- **WHEN** `make help`, `make format`, `make lint-python`, `make test-agents-collect` are run
- **THEN** each exits with code 0 and produces expected output

#### Scenario: Build targets
- **WHEN** `make build-app` is run
- **THEN** the plugin builds successfully (tsc + rollup exit 0)

#### Scenario: Test targets
- **WHEN** `make test-app` is run
- **THEN** jest tests pass

#### Scenario: Release targets
- **WHEN** `make changelog`, `make release-notes`, `make bump-local`, `make squash-commits` are run
- **THEN** each produces expected output without errors

#### Scenario: Loop-harness stages
- **WHEN** each stage of `make loop-harness` is run individually
- **THEN** each stage completes with PASS/FAIL/SKIP status

#### Scenario: OpenSpec workflow targets
- **WHEN** `make openspec-new`, `make wt-create`, `make validate-ts`, `make format-ts` are run
- **THEN** each produces expected output or completes successfully
