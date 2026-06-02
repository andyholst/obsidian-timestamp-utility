# Developer — Action Plan

## Objective
Delete dead code, fix broken tests, harden the eval gate, and ensure the workflow truly blocks slop before integration.

## Tasks

### DEV-01: Dead Code Deletion
Delete all files identified in the audit report as dead code. **Order matters** — delete leaf nodes first.

**Phase 1a: Root-level scratch files** (no dependencies):
```
_check_compat.py, _check_path.py, _check_rc.py, _check_rc2.py,
_check_versions.py, _debug.py, _fix_deps.py, _reload_test.py,
_test_debug.py, _test_debug2.py, _test_imports.py, _test_manual.py,
fix_integration_tests.py
```

**Phase 1b: Dead agent files** (not imported by any live code):
```
src/code_validator.py
src/code_generator_agent.py
src/collaborative_generator.py
src/composable_workflows.py
src/test_suite_examples.py
src/llm_validator.py
src/ticket_clarity_agent.py
src/code_integrator_agent.py
src/code_extractor_agent.py
src/test_generator_agent.py
src/error_recovery_agent.py
src/pre_test_runner_agent.py
src/process_llm_agent.py
src/post_test_runner_agent.py
src/combined_agents.py
src/prompts.py
src/state_adapters.py
src/performance.py
src/base_agent.py
src/dependency_analyzer_agent.py
src/feedback_agent.py
src/implementation_planner_agent.py
src/agent_composer.py
src/tool_integrated_agent.py
src/tool_integrated_code_generator_agent.py
src/clients.py
src/fetch_issue_agent.py
src/collect_tests.py
src/analyze_usage.py
src/parse_executed_tests.py
src/hitl_node.py
src/tool_executor.py
src/output_result_agent.py
src/api_validation_tools.py
src/workflows.py
```

**Verification after deletion**:
```bash
cd agents/agentics && .venv/bin/python -c "from src.agentics import AgenticsApp; print('OK')"
```

### DEV-02: Fix Broken Tests

**test_workflow_integration.py** — Complete rewrite needed:
- Remove tests referencing `_route_after_generate`, `_node_validate`, `_node_integrate`
- Replace with tests for the actual eval gate behavior:
  - `test_eval_gate_blocks_integration_on_low_score`
  - `test_eval_gate_allows_integration_on_high_score`
  - `test_eval_gate_records_failure_criteria`
  - `test_regression_tracker_saves_baseline_on_pass`

**test_test_suite_integration.py** — Update to use GoldStandardSuite:
- Replace old test_suite format references
- Add integration test: add case → run workflow → verify score against case threshold

**test_tool_integrated_agent_integration.py** — Delete (tests dead code)

### DEV-03: Harden Eval Gate in Workflow

**Current issue**: The `_node_generate_code_tests` method generates code, scores it, but the integration path may still write files even when the gate fails.

**Fix**: Ensure this structure:
```python
# In _node_generate_code_tests:
# 1. Generate code (up to 3 attempts with self-correction)
# 2. Score with score_output()
# 3. Gate check with gate_check()
# 4. IF pass → integrate (write to main.ts, addCommand)
# 5. IF fail → record failure, set integrated=False, return state WITHOUT writing
```

**Key change**: The `if gen_code:` block that writes to `main.ts` must be inside the `if passed:` block.

### DEV-04: Feed Eval Scores to LLM Retry

**Current issue**: The 3-attempt retry loop only checks structural errors (class/import/missing export) but doesn't use eval_rubric scores.

**Fix**: After each failed attempt:
```python
# Score the generated code
ev = score_output({**state, "generated_code": gen_code, "generated_tests": gen_test_code})
if not ev["passed"]:
    failure = record_failure({**state, "generated_code": gen_code}, ev)
    # Include failure context in retry prompt
    error_ctx = f"Score: {ev['total']:.2f}/1.0. Failed: {', '.join(failure['failed_criteria'])}. Fix: {'; '.join(failure['what_to_fix'])}"
```

### DEV-05: Add Regression Check After Integration

After successful integration, run regression check:
```python
# After successful integration:
tracker = RegressionTracker()
regression = tracker.check_regression(ev)
state["regression_check"] = regression
if regression.get("has_baseline") and regression["regressed"]:
    log_info("regression", f"Quality regression detected: {regression['total_delta']:.4f}")
```

## Deliverables
- DEV-01: All dead code deleted, import chain verified
- DEV-02: Broken tests fixed/rewritten, all 227+ tests pass
- DEV-03: Eval gate hardened — integration blocked on low score
- DEV-04: LLM retry uses eval scores as feedback
- DEV-05: Regression check runs after integration

## Sign-off Criteria
- `grep -r "from \.code_validator\|from \.collaborative_generator\|..." agents/agentics/src/` returns zero results
- `.venv/bin/python -c "from src.agentics import AgenticsApp"` succeeds
- All unit tests pass: `make test-agents-unit-mock` equivalent
- Eval gate test: score < 0.7 → no file writes to main.ts
- Retry test: LLM receives eval failure context in retry prompt
