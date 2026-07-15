# Proposal: HITL is Opt-In and Loop-Excluded

## Why
The `HITLNode` (`agents/agentics/src/hitl_node.py`) is a conditional human-review node.
It only prompts a human (calls `input()`) when **all** of these hold: validation score
< 80, not in CI, `HITL_ENABLED=1`, `INTERACTIVE_HITL=1`, and `stdin.isatty()`. In the
loop / CI / `make run-agentics` automated runs none of those hold, so the node returns
`state` unchanged — it is a **no-op pass-through**. This has caused recurring confusion:
reviewers assume the "human-in-the-loop" must fire in the loop, and a test
(`test_collaborative_hitl_e2e.py::test_hitl_node`) asserts `'human_feedback' in state`,
which that key is only ever added on a real interactive TTY run — never in the loop. That
assertion is flaky/misleading and should be re-pointed at the pass-through behaviour.

This change formalizes, in the spec, that HITL is a **deliberate opt-in feature for a human
at a terminal**, explicitly **excluded from all automated loop/CI runs**, and that the
`human_feedback` state key is only present on those interactive runs.

## What Changes
- Add capability `hitl-optin` with one ADDED Requirement: HITL MUST be disabled (pass-through)
  unless explicitly opted in via `HITL_ENABLED=1` AND `INTERACTIVE_HITL=1` AND a real TTY;
  it MUST NOT block automated/loop/CI runs.
- Add a Scenario proving the loop-exclusion (no prompt, state unchanged, no
  `human_feedback` key) and one proving the opt-in path (human at TTY adds `human_feedback`).
- Cross-reference `agentic-self-correct-loop` (B7.1 fast-mode still routes through the node,
  but the node is a no-op there) and the existing `hitl_node.py` two-flag gate.
- Update `test_collaborative_hitl_e2e.py::test_hitl_node` to assert the **pass-through**
  behaviour under loop/non-interactive conditions (no `human_feedback` expected), not the
  interactive-only key. (The interactive happy-path can stay as a separate,
  properly-gated test if desired.)

## Capabilities
- `hitl-optin` — Human-in-the-Loop review is opt-in and never blocks automated runs.

## Impact
- Files: `agents/agentics/src/hitl_node.py` (unchanged — already correct), the HITL test
  (`test_collaborative_hitl_e2e.py`), and docs (`AGENTS.md` / skill cross-reference optional).
- Behaviour: NONE in the loop (already a no-op). Only the spec + one test assertion change.
- Risk: low. No production code behaviour changes; the node stays a live opt-in feature.
