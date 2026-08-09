# Makefile Verification Tasks

## Simple targets (no containers)
- [x] 1.1 Test `make help` — shows help message
- [x] 1.2 Test `make format` — formats Python code with ruff
- [x] 1.3 Test `make lint-python` — runs ruff linting
- [x] 1.4 Test `make test-agents-collect` — CI guard for collection errors
- [ ] 1.5 Test `make validate-ts` — TypeScript validation with tsc
- [x] 1.6 Test `make format-ts` — Prettier formatting

## Build targets
- [x] 2.1 Test `make build-app` — builds plugin via nerdctl compose
- [x] 2.2 Test `make test-app` — runs jest tests (has TypeScript type issues to investigate)

## Release flow targets
- [ ] 3.1 Test `make changelog` — generates CHANGELOG.md
- [x] 3.2 Test `make release-notes` — refreshes README release notes
- [x] 3.3 Test `make bump-local` — local version bump
- [ ] 3.4 Test `make squash-commits` — squashes commits ahead of main
- [ ] 3.5 Test `make release-prep` — local publish prep
- [ ] 3.6 Test `make release-flow` — canonical release flow (local only)

## Loop-harness stages
- [x] 4.1 Test `make loop-collect` — hermetic collection guard
- [x] 4.2 Test `make loop-ts-floor` — TS test/command floor
- [ ] 4.3 Test `make loop-unit` — hermetic unit tests
- [ ] 4.4 Test `make loop-unit-real` — real agent unit tests (live Ollama)
- [ ] 4.5 Test `make loop-integration` — broad agentic integration suite
- [x] 4.6 Test `make loop-build-app` — build the Obsidian plugin
- [x] 4.7 Test `make loop-test-app` — run jest on the plugin (has TypeScript type issues)

## OpenSpec workflow targets
- [x] 5.1 Test `make openspec-new` — scaffold an OpenSpec change
- [ ] 5.2 Test `make wt-create` — create isolated git worktree
- [ ] 5.3 Test `make validate-ts` — TypeScript validation
- [ ] 5.4 Test `make format-ts` — Prettier formatting

## Other targets
- [x] 6.1 Test `make check-docs-sync` — B8 doc/loop sync gate
- [x] 6.2 Test `make generate-requirements` — regenerate requirements.txt
- [x] 6.3 Test `make install-git-hooks` — install git hooks
- [x] 6.4 Test `make clean` — cleanup targets
- [x] 6.5 Test `make stop-containers` — stop running containers

## Final verification
- [ ] 7.1 Run `make loop-harness` end-to-end
- [ ] 7.2 Run `make openspec validate makefile-verify` — verify change is green
- [ ] 7.3 Document all results in agent-wiki
