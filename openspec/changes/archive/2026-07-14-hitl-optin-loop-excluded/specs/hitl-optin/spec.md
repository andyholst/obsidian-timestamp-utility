## ADDED Requirements

### Requirement: HITL is opt-in and never blocks automated runs
The `HITLNode` MUST NOT prompt a human or block execution in automated, CI, or loop-harness
runs. It MUST be a pass-through (return `state` unchanged, no `human_feedback` key) unless
ALL of the following are true: validation score `< 80`, not in a CI environment,
`HITL_ENABLED=1`, `INTERACTIVE_HITL=1`, and `sys.stdin.isatty()` is true.

#### Scenario: Loop / CI exclusion (no prompt, no human_feedback)
- **WHEN** the pipeline runs under the loop harness, CI, or any non-interactive context (no TTY, or `HITL_ENABLED`/`INTERACTIVE_HITL` not both set)
- **THEN** `HITLNode.invoke` returns the state unchanged, performs no `input()` prompt, and the resulting state does NOT contain a `human_feedback` key

#### Scenario: Opt-in interactive review adds human_feedback
- **WHEN** a human runs with `HITL_ENABLED=1` and `INTERACTIVE_HITL=1` at a real TTY and the validation score is below threshold
- **THEN** the node prompts for review and returns a state copy containing `human_feedback`

### Requirement: HITL test asserts pass-through, not the interactive key
Any automated integration test for `HITLNode` MUST assert the **pass-through** behaviour
under non-interactive conditions (state unchanged, no `human_feedback`), because the
`human_feedback` key is only produced on an interactive TTY run and MUST NOT be expected in
the loop.

#### Scenario: Non-interactive HITL test passes without human_feedback
- **WHEN** a test invokes `HITLNode` without `INTERACTIVE_HITL=1` / TTY
- **THEN** the test asserts the returned state is unchanged and lacks `human_feedback`, rather than failing because that key is absent
