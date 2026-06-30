# VERIFICATION.md — Task-Specific Verification Criteria

## Feature Implementation (new command, UI component, or agent tool)
- [ ] Implementation complete and registered in plugin (if applicable)
- [ ] `make test-app` passes (strict TS compiles, Jest green)
- [ ] No type errors (`tsc --noEmit` clean)
- [ ] Tests cover the happy path and at least one edge case
- [ ] No desktop-only APIs used (Obsidian mobile compat)
- [ ] Follows patterns from existing commands (consistent style)
- [ ] No hardcoded secrets or tokens

## Bug Fix
- [ ] Reproduces the bug (test case or manual steps)
- [ ] Root cause identified and documented
- [ ] Fix applied (minimal, targeted)
- [ ] Regression test added (prevents same bug twice)
- [ ] Doesn't break existing functionality (`make test-app` green)

## Plugin Build & Release
- [ ] `dist/main.js` built via `make build-app`
- [ ] `manifest.json` version matches `package.json` exactly
- [ ] `make release` produces ZIP in `release/`
- [ ] CHANGELOG.md updated
- [ ] Git tag created for version

## Agent / Agentics Change
- [ ] `make test-agents-unit-mock` passes (no Ollama needed)
- [ ] `make test-app` passes (generated code compiles + all tests green)
- [ ] Agent tests cover new behavior
- [ ] `make lint-python` clean (ruff + mypy)
- [ ] Text→Pseudocode→Code pipeline: pseudocode extraction, safety filtering, deterministic code construction
- [ ] Eval gate: 7-criteria scoring, hard gates (code-test consistency, tests_pass==0.0), threshold 0.4
- [ ] Test generation: deterministic from export_name (no LLM hallucination)
- [ ] Self-correction: retry loop with eval_failure_context feedback
- [ ] ARCHITECTURE.md updated to reflect pipeline changes

## Refactoring
- [ ] Preserves exact behavior (`make test-app` green before AND after)
- [ ] Improves measurable quality (readability, performance, type safety)
- [ ] No functionality removed without explicit approval
- [ ] Minimal diff — only what's needed

## Documentation
- [ ] README.md updated (if user-facing change)
- [ ] Docstrings added for public functions/classes
- [ ] Complex logic has inline comments explaining "why"
- [ ] AGENTS.md updated if process changed
