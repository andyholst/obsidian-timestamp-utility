# AGENTS.md — Loop Protocol

## Core
- **Makefile + Dagger only**: Run `make help` first. `make setup-dev` for Dagger/engine. **Never** run npm/docker/ollama/Python directly. Trust Makefile/Dagger pipelines over README.md.
- Env: Set `GITHUB_TOKEN` (agents), `OLLAMA_MODEL=qwen3.5:9b` (default), `OLLAMA_CODE_MODEL=qwen3.5:9b`. Use `make check-deps check-github check-mcp`.
- Structure: `src/` (Obsidian TS plugin), `agents/agentics/` (LangGraph agents + tests), `dagger-pipeline/` (all build/test logic). Plugin edits independent of agents.
- Cleanup: `make clean`, `make clean-dagger-engine` or `make nuke-dagger` for Dagger issues. `make fix-perms` auto-runs after most targets.

---

## Loop Protocol

```
1. READ   → task, code, tests, Makefile, AGENTS.md, VISION.md, STATE.md, VERIFICATION.md
2. PLAN   → what changes, what to verify, todo list (decompose per rules below)
3. BUILD  → make build-app / make test-app (fix → retry on failure)
4. RUN    → manual install or agent test target (fix → retry on failure)
5. VERIFY → run all 5 layers (see below)
6. CHECK  → run VISION.md anti-drift checks
7. DECIDE → green? commit+push. red? → go to 3. failed 3x? → escalate to human.
```

**Rules:**
- Max 10 iterations per task. If stuck after 10, report exact failure + why.
- One change at a time. Verify after each.
- Never commit broken code. Branch must always build + test clean.
- Update STATE.md after every run.

---

## Verification Layers (L1-5)

After every change, verify ALL layers. Do NOT skip layers.

### Layer 1 — Automated (fast, always run)
```bash
make test-app          # TypeScript strict compiles + Jest passes
tsc --noEmit           # Type check without emit (belt + suspenders)
```

### Layer 2 — Tests (standard correctness)
```bash
make test-app          # All tests pass
# For agents:
make test-agents-unit-mock   # Mocked, no Ollama needed
make lint-python             # ruff + mypy clean
```
- If tests fail → loop attempts fix before proceeding
- Coverage target: >= 80% for new code

### Layer 3 — Spec Compliance (strict)
- Read VISION.md criteria
- Check output meets each criterion objectively
- For plugin: verify command registered, manifest correct, no desktop-only APIs
- For agents: verify graph transitions, MCP starts, tests target real issues

### Layer 4 — Security (before commit)
- No hardcoded secrets in new code
- Dependencies pinned (package-lock.json committed)
- Plugin uses only Obsidian API (no eval, no child_process)
- Agent MCP tools scoped (no arbitrary file delete, no force push)

### Layer 5 — LLM Judge (high-stakes changes ONLY)
Trigger when:
- New command or UI component added
- Agent graph structure changed
- Release process modified
- 2+ consecutive failures on same task type

Use `delegate_task` with stronger model:
```
"You are a senior engineer. Review this change against VERIFICATION.md criteria.
Score 1-10 on: correctness, readability, security, test coverage.
Explain reasoning. Flag any concerns."
```
Threshold: Score >= 8 on all dimensions to pass.

---

## Task Decomposition Rules

Before executing, break tasks into:
1. What exactly needs to change?
2. What are the acceptance criteria? (from VERIFICATION.md)
3. What's the smallest verifiable step?
4. What could go wrong? (pre-mitigate)

Output: numbered todo list with acceptance criteria per item.

**Agent-Sized Task Criteria:**
- Specific and unambiguous
- Has clear acceptance criteria
- Small enough to complete in ≤5 loop iterations
- Verifiable (objective pass/fail)

---

## Permission Boundaries

### Can Edit
- `src/`, `tests/`, `agents/`, `dagger-pipeline/`, `scripts/`
- `Makefile`, `package.json`, `manifest.json`, `tsconfig.json`
- `AGENTS.md`, `VISION.md`, `STATE.md`, `VERIFICATION.md`
- `CHANGELOG.md`, `README.md`

### Cannot Edit
- `.git/`, `.env`, production configs
- `node_modules/`, `dist/` (use `make build-app` instead)

### Cannot Do
- Push to main (feature branches only)
- Delete files in project root
- Force push or squash/rebase commits
- Commit secrets or tokens
- Run npm/docker/ollama/Python directly (use Makefile/Dagger)

### Must Do
- Commit to feature branch
- Push via standard `git push`
- Bump version in both `package.json` + `manifest.json` before release

---

## Escalation Rules

- **1st failure:** self-correct, try alternative approach
- **2nd failure:** try fundamentally different approach
- **3rd failure:** STOP. Report to human with:
  - What was attempted
  - What failed each time
  - Current code state
  - Suggested next steps

---

## Model Routing

| Task Type | Model |
|-----------|-------|
| Simple fixes (lint, formatting, typo) | default (qwen3.5) |
| New command / UI component | qwen3.5 + LLM Judge |
| Agent graph changes | qwen3.5 + LLM Judge |
| Architecture / debugging | strongest available |
| LLM-as-Judge | strongest available |
| Batch/parallel subtasks | default per sub-agent |

---

## Logging Protocol

- Log every loop iteration: goal, steps taken, result (pass/fail)
- Log every fix attempt: what was tried, what happened
- On failure: log full context (code state, error message, attempted fixes)
- Update STATE.md after every run (run log + cost + evaluation metrics)

## CI as Verification Gate

CI (`make test-app` on non-main) IS Layers 1-4:
- Build compiles → L1
- Tests pass → L2
- Spec compliance → L3 (anti-drift checks)
- Security → L4 (no secrets, pinned deps)

**Feedback loop on CI failure:**
1. Read CI output
2. Fix the issue
3. Re-push
4. Record failure mode in STATE.md

## Gradual Expansion Policy

Trust ramp for autonomous operation:
- **Weeks 1-2:** Human reviews every diff
- **Weeks 3-4:** Human reviews 50% of diffs
- **Month 2+:** Statistical sampling (10% of diffs)
- **Architecture / high-risk / release process:** Always human review

---

## Plugin (src/)
- Entry: `src/main.ts` (6 commands: timestamp insert/rename variants, date-range modal, reminder-to-task processor).
- Build/test: `make test-app` (Rollup CJS to dist/main.js + Jest in src/__tests__/). No separate lint; strict TS.
- Install: Copy `dist/main.js` + `manifest.json` to `.obsidian/plugins/timestamp-utility/` (exact match to manifest.id; avoid desktop-only APIs).
- CI: Only `make test-app` on non-main. Bump version in both package.json + manifest.json.
- **Never edit dist/**. Use `make build-app` before manual testing.

## Agents (agents/agentics/)
- Multi-agent LangGraph system (ticket → plan → codegen → test → review → integrate) with MCP on :3003.
- Quick verify: `make test-agents-unit-mock` (mocked, no Ollama).
- Full: `make start-mcp-persist &` then `make test-agents` or `make run-agentics ISSUE_URL=...` (needs GITHUB_TOKEN, live Ollama, TEST_ISSUE_URL).
- Tests target real issues (#20, #22, #23). Use `make lint-python` (ruff/mypy). Verbose/watch targets exist.

## Release
- `make release` after version bump (builds changelog + ZIP in release/).
- No pre-commit hooks. Avoid committing secrets.

## Gotchas
- MCP **must** run in background for any agentics, integration, or run-agentics.
- Dagger engine state is fragile; use dedicated start/stop/clean targets.
- README has outdated install paths/env vars — follow Makefile.
- For Obsidian plugin work only, ignore agents/ entirely.
