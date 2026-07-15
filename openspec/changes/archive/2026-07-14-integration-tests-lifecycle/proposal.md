# Proposal: integration-tests-lifecycle

## Why
The loop-harness stage (`make loop-harness`) runs unit → e2e → build-app → test-app, but the
**broad integration suite** (`agents/agentics/tests/integration/*`, 34 files) is NOT a tracked
gate and has drifted:
- Several files are dead duplicates (`test_jest_execution_integration_fixed.py`,
  `test_jest_execution_minimal.py`) that should be deleted per the project rule
  "red tests: dead ⇒ delete, valid ⇒ refactor hermetic, update tasks.md from findings".
- Several `phase1..phase5` lifecycle files overlap `test_agentics_app_integration.py` /
  `test_composable_workflows_integration.py`.
- Whether each integration test is hermetic (mocked) vs live (needs `GITHUB_TOKEN`/`OLLAMA_HOST`)
  is undocumented, so a broken test is indistinguishable from a skipped one.

The user explicitly asked to (a) create OpenSpec tasks proving the integration tests work and
are updated (not just dead tests), and (b) update AGENTS.md / hermes/skills/openspec-loop-harness.md
/ the Makefile so integration tests are part of the loop/harness engineering.

## What Changes
1. **Audit + categorize** every integration test into: hermetic / live-Ollama / live-GitHub / dead.
2. **Delete dead duplicates**; keep one canonical file per concern. Herness convention: one file per
   agent (`test_<agent>_integration.py`), plus the durable B1 e2e harness (`test_change_driven_*`).
3. **Hermeticize** valid-but-live tests where the live call is not the assertion (mock GitHub/Ollama).
4. **New Makefile gate** `loop-integration` inserted as step 2.5 of `loop-harness` (runs the
   integration suite; live tests skip cleanly without `GITHUB_TOKEN`/`OLLAMA_HOST`).
5. **AGENTS.md + skill** updated: add behaviour **B17** — integration suite is a mandatory loop phase,
   dead-test deletion rule codified, live tests must skip cleanly when services are absent.

## Capabilities
- `integration-tests-lifecycle` (new capability, delta)

## Impact
- Files: `agents/agentics/tests/integration/*` (audit + prune), `Makefile` (loop-integration),
  `AGENTS.md`, `hermes/skills/openspec-loop-harness.md`.
- No TS/plugin code touched. No Python agentic code changed except test files.
- B4/B14 honored: archive does not commit/push; committing is a deliberate human step.
