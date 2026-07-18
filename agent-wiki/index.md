# Agent Wiki Index

This wiki documents work done on OpenSpec changes for the **obsidian-timestamp-utility** project.

## How this wiki is maintained

- Hermes creates one entry per completed OpenSpec change using the `record-work` skill.
- Entries follow the naming convention: `YYYY-MM-DD-<change-folder-name>.md`.
- Weekly summaries live in `weekly-summaries/`.

## Change Entries
- [2026-07-18-make-always-background](2026-07-18-make-always-background.md) — Summary
- [2026-07-17-pr-review-no-squash](2026-07-17-pr-review-no-squash.md) — Summary
- [2026-07-17-uuid-modal-agentic-generation](2026-07-17-uuid-modal-agentic-generation.md) — Summary
- [2026-07-16-loop-harness-secret-scan](2026-07-16-loop-harness-secret-scan.md) — Summary
- [2026-07-16-secret-scan-show-findings](2026-07-16-secret-scan-show-findings.md) — Summary
- [2026-07-16-replace-trufflehog-with-gitleaks](2026-07-16-replace-trufflehog-with-gitleaks.md) — Summary
- [2026-07-16-lint-fix-trailing-whitespace](2026-07-16-lint-fix-trailing-whitespace.md) — Summary
- [2026-07-16-readme-architecture-overview](2026-07-16-readme-architecture-overview.md) — Summary
- [2026-07-16-request-to-openspec](2026-07-16-request-to-openspec.md) — Summary
- [2026-07-16-readme-align-with-commits](2026-07-16-readme-align-with-commits.md) — Summary
- [2026-07-15-uuid-modal-agentic-generation](2026-07-15-uuid-modal-agentic-generation.md) — Summary
- [2026-07-15-harden-docker-run-oneshell](2026-07-15-harden-docker-run-oneshell.md) — Summary
- [2026-07-15-ztest-archive-order](2026-07-15-ztest-archive-order.md) — Summary
- [2026-07-15-phase7-archive-containerized](2026-07-15-phase7-archive-containerized.md) — work-log entry for `phase7-archive-containerized`
- [2026-07-15-strict-ts-test-floor](2026-07-15-strict-ts-test-floor.md) — added `loop-ts-floor` guard (stage 0.5): fails the loop if TS test/command counts drop below `origin/main`; fixed `main.test.ts` uuid/base64 test regression.

- [2026-07-15-doc-sync-tests](2026-07-15-doc-sync-tests.md) — derived-contract B8 doc/loop-sync gate (no hardcoded constants) + per-file NEGATIVE tests proving RED when a B-step/stage/make-target is removed from ANY of the 5 sync files; `b9-perms` wired as a Makefile prerequisite.

- [2026-07-13-uuid-modal-agentic-generation](2026-07-13-uuid-modal-agentic-generation.md) — deterministic floor green (`run-agentics`→`build-app`→`test-app` PASS); no hard-coded TS in Python (B10).
- [2026-07-14-python-agentic-slim-refactor](2026-07-14-python-agentic-slim-refactor.md) — analysis-driven slim: removed dead/unused Python + the B10/B11-violating ultra-fast inline block; fixed fast-mode floor bypass (B7.1) + uuid-specific contract parser; 3 e2e (ticket20/22/greetings) GREEN; `make run-agentics` gates pass.
- [2026-07-14-fix-fetch-issue-agent-tests](2026-07-14-fix-fetch-issue-agent-tests.md) — triaged 4 red tests; refactored valid ones hermetic (B15 bridge + mocked LLM); full unit suite 517/517 GREEN.
- [2026-07-14-audit-mcp-slim-refactor-integrity](2026-07-14-audit-mcp-slim-refactor-integrity.md) — re-audit of the MCP slim-refactor: caught 3 orphaned breakages (conftest MCP imports, `test_tool_integration_patterns` → `src.agentics.mcp_tools`, `test_scenarios.py` MCP mocks); all resolved + verified **516 unit / 200 integration collect clean, e2e B5/B6 guards intact**.

## Weekly Summaries

- [Week 28, 2026](weekly-summaries/2026-W28.md) _(to be created)_

## Structure

```
agent-wiki/
├── index.md                     ← this file
├── 2026-07-13-<change>.md      ← created by Hermes per change
└── weekly-summaries/
    └── 2026-W28.md
```
