# DevSecOps Team — Dead Code Audit & Architecture Alignment

## Date: 2026-05-31

## Executive Summary

The agentics codebase has **16,747 lines across 49 source files** but only **8 files are actually imported** by the two entry points (`workflow.py` and `agentics.py`). The remaining **41 source files (~12,000 lines) are dead code** — agent-based architectures from a previous design that was replaced by the LangGraph workflow approach. Additionally, **7 root-level debug/scratch files** and **several broken test files** referencing removed functions need cleanup.

This audit identifies every gap, every piece of dead code, and provides a step-by-step refactoring plan aligned with fix_the_slop.md quality principles.

---

## 1. Import Chain Analysis

### Live Code (actually imported at runtime)

**Entry point 1: `src/workflow.py`** imports:
- `.config` (AgenticsConfig)
- `.state` (State)
- `.utils` (log_info, remove_thinking_tags)
- `.eval_rubric` (score_output, gate_check, record_failure, RubricStore, RegressionTracker)

**Entry point 2: `src/agentics.py`** imports:
- `.config` (AgenticsConfig, init_config)
- `.eval_rubric` (score_output, gate_check, RubricStore)
- `.exceptions` (AgenticsError, ValidationError)
- `.monitoring` (structured_log)
- `.production_monitor` (run_production_check, close_the_loop)
- `.services` (init_services)
- `.utils` (log_info, validate_github_url)
- `.workflow` (AgenticsWorkflow)
- `.test_suite` (GoldStandardSuite)

**Transitive imports** (imported by the above):
- `.models` (imported by `services.py`)
- `.circuit_breaker` (imported by `services.py`)
- `.mcp_client` (imported by `services.py`)

### Dead Code (never imported by any live path)

**Agent-based architecture (previous design, ~8,000 lines):**
| File | Lines | What it was | Why dead |
|------|-------|-------------|----------|
| `code_validator.py` | 1,209 | Multi-stage code validation pipeline | Replaced by eval_rubric + gate_check |
| `code_generator_agent.py` | 1,103 | Agent-based code generation | Replaced by LLM direct generation in workflow |
| `collaborative_generator.py` | 962 | Multi-agent collaborative generation | Replaced by single LLM with self-correction loop |
| `composable_workflows.py` | 1,108 | Composable workflow components | Replaced by LangGraph StateGraph |
| `test_suite_examples.py` | 924 | Test suite example data | Obsolete format, replaced by GoldStandardSuite |
| `llm_validator.py` | 563 | LLM-as-validator agent | Replaced by eval_rubric scoring |
| `ticket_clarity_agent.py` | 549 | Ticket analysis agent | Functionality in workflow._node_clarify_ticket |
| `code_integrator_agent.py` | 548 | Code integration agent | Functionality in workflow._node_generate_code_tests |
| `code_extractor_agent.py` | 533 | Code extraction agent | Functionality in workflow._node_extract_code |
| `test_generator_agent.py` | 460 | Test generation agent | LLM generates tests directly in workflow |
| `error_recovery_agent.py` | 426 | Error recovery agent | Self-correction loop in workflow |
| `pre_test_runner_agent.py` | 282 | Pre-test validation agent | Not used in current flow |
| `process_llm_agent.py` | 275 | LLM processing agent | Replaced by direct LLM calls |
| `post_test_runner_agent.py` | 261 | Post-test analysis agent | Replaced by eval gate |
| `combined_agents.py` | 309 | Agent composition layer | No longer needed |
| `prompts.py` | 296 | Prompt templates for agents | Not referenced by current code |
| `state_adapters.py` | 289 | State adapter layer | Single State TypedDict replaces this |
| `performance.py` | 458 | Performance monitoring | Monitoring.py provides this |
| `base_agent.py` | 145 | Base agent class | No agents use this |
| `dependency_analyzer_agent.py` | 150 | Dependency analysis agent | Not in current flow |
| `feedback_agent.py` | 148 | Feedback processing agent | Replaced by close_the_loop mechanism |
| `implementation_planner_agent.py` | 117 | Planning agent | Functionality in workflow._node_plan_implementation |
| `agent_composer.py` | 93 | Agent composition | No longer needed |
| `tool_integrated_agent.py` | 91 | Tool-integrated agent base | Not used |
| `tool_integrated_code_generator_agent.py` | 194 | Tool-integrated code gen | Not used |
| `clients.py` | 90 | Client utilities | Services.py replaces this |
| `fetch_issue_agent.py` | 81 | Issue fetching agent | Functionality in workflow._node_fetch_issue |
| `collect_tests.py` | 79 | Test collection utility | Not used |
| `analyze_usage.py` | 75 | Usage analysis | Not used |
| `parse_executed_tests.py` | 59 | Test parsing | Not used |
| `hitl_node.py` | 46 | Human-in-the-loop node | Not used |
| `tool_executor.py` | 36 | Tool execution layer | Not used |
| `output_result_agent.py` | 27 | Output formatting agent | workflow._node_output replaces this |
| `api_validation_tools.py` | 241 | API validation tools | Not used |
| `workflows.py` | 236 | Alternative workflow definitions | Not used |

**Root-level scratch/debug files (never imported):**
| File | Lines | Purpose |
|------|-------|---------|
| `_check_compat.py` | 10 | Compatibility check (stale) |
| `_check_path.py` | 2 | Path check (stale) |
| `_check_rc.py` | 6 | RC check (stale) |
| `_check_rc2.py` | 11 | RC check v2 (stale) |
| `_check_versions.py` | 8 | Version check (stale) |
| `_debug.py` | 63 | Debug utilities (stale) |
| `_fix_deps.py` | 11 | Dependency fix (stale) |
| `_reload_test.py` | 8 | Reload test (stale) |
| `_test_debug.py` | 17 | Test debug (stale) |
| `_test_debug2.py` | 6 | Test debug v2 (stale) |
| `_test_imports.py` | 19 | Import test (stale) |
| `_test_manual.py` | 46 | Manual test (stale) |
| `fix_integration_tests.py` | 291 | Integration test fixer (stale) |

---

## 2. Test File Audit

### Tests referencing removed functions/code

| Test File | Issue | Action |
|-----------|-------|--------|
| `test_workflow_unit.py` | References non-existent `_validate_method_inside_class` | ✓ Already fixed |
| `test_workflow_edge_cases.py` | TestConditionalRouting referenced `_route_after_validate` | ✓ Already fixed |
| `test_workflow_integration.py` | References `_route_after_generate`, `_node_validate`, `_node_integrate` | Needs rewrite |
| `test_test_suite_integration.py` | Tests old test_suite format | Needs rewrite |
| `test_tool_integrated_agent_integration.py` | Tests dead `tool_integrated_agent` | Delete (tests dead code) |
| `test_ticket20/22_e2e_integration.py` | Full E2E with Ollama + GitHub | Keep but mark as integration-only |
| `test_eval_rubric_enhanced.py` | Tests new eval_rubric | ✓ Keep |
| `test_production_monitor_enhanced.py` | Tests new production_monitor | ✓ Keep |
| `test_regression.py` | Tests new RegressionTracker | ✓ Keep |
| `test_test_suite.py` | Tests new GoldStandardSuite | ✓ Keep |

---

## 3. Architecture Gaps (vs fix_the_slop.md)

### Gap 1: No Pre-Integration Gate in Workflow
**Issue**: The eval_rubric scoring exists but the workflow's `_node_generate_code_tests` does NOT gate integration on the score. The gate code was partially added by workers but the integration path still writes to main.ts regardless of score in some code paths.

**Fix**: Ensure the eval gate is BEFORE file writes, with clear pass/fail routing.

### Gap 2: Self-Correction Loop Doesn't Use Eval Scores
**Issue**: The 3-attempt retry loop in `_node_generate_code_tests` only checks structural errors (class/import/missing export) but doesn't feed eval_rubric scores back to the LLM.

**Fix**: After each attempt, run `score_output()` and include the scores + `record_failure()` output in the retry prompt.

### Gap 3: No Regression Check After Integration
**Issue**: The workflow integrates code and runs tests, but doesn't compare the current eval score against a baseline.

**Fix**: After successful integration, run `RegressionTracker.check_regression()` and log the result.

### Gap 4: Production Monitor Not Wired to Cron
**Issue**: `run_production_check()` exists but no cron job calls it.

**Fix**: Add a cron job or scheduled task that runs `run_production_check()` and delivers alerts.

### Gap 5: Test Generator Doesn't Validate Its Own Output
**Issue**: The LLM generates Jest tests but there's no eval_rubric criteria that scores test quality directly.

**Fix**: Add test quality as a sub-criterion in the eval rubric (test coverage, assertion count, describe/it structure).

### Gap 6: No Gold Standard Cases Populated
**Issue**: `GoldStandardSuite` exists but has no cases. Without gold standards, regression testing has no baseline.

**Fix**: Populate initial gold standards from known-good outputs.

### Gap 7: Orphaned Monitoring Infrastructure
**Issue**: `monitoring.py` has `PerformanceMonitor`, `MetricsStore`, `WorkflowTracker` classes that are never instantiated by the workflow.

**Fix**: Either wire them in or remove them. Dead monitoring is worse than no monitoring — it gives false confidence.

### Gap 8: Circuit Breaker Integrity
**Issue**: The circuit breaker (`circuit_breaker.py`) wraps service calls but failures in the circuit breaker itself (e.g., `ServiceHealthMonitor` returning wrong state) are not tested.

**Fix**: Add negative test cases for circuit breaker failure modes.

---

## 4. Refactoring Plan

### Phase 1: Dead Code Elimination (P0)
**Goal**: Remove all files not in the import chain.

**Steps**:
1. Verify no external scripts reference dead files: `grep -r "from.*agentics" agents/agentics/ --include="*.py" | grep -v "src/"`
2. Delete all dead source files from `src/`
3. Delete all root-level scratch files
4. Delete/update broken test files
5. Run full test suite to confirm nothing broke
6. Run `make lint-python`
7. Verify line count reduction

**Expected outcome**: ~16,747 → ~3,500 lines (~79% reduction)

### Phase 2: Eval Loop Hardening (P0)
**Goal**: Ensure the eval gate truly blocks slop before integration.

**Steps**:
1. Audit `_node_generate_code_tests` for the eval gate placement
2. Ensure `gate_check()` result controls integration (no file writes on fail)
3. Feed `record_failure()` output back into LLM retry prompts
4. Add regression check after successful integration
5. Write tests for the gate behavior (pass/fail/retry)

### Phase 3: Monitoring Wiring (P1)
**Goal**: Connect production monitoring to actual workflow runs.

**Steps**:
1. Wire `PerformanceMonitor` into workflow nodes (or remove it)
2. Wire `WorkflowTracker` into LangGraph lifecycle
3. Add RubricStore recording at every node transition
4. Create cron-compatible monitoring script
5. Add degradation alert delivery (not just return value)

### Phase 4: Gold Standard Population (P2)
**Goal**: Populate gold standard test cases for regression testing.

**Steps**:
1. Identify 5-10 known-good outputs from previous runs
2. Add them to `GoldStandardSuite` via `add_case()`
3. Create `run_regression_suite()` in `AgenticsApp`
4. Add regression check to post-integration flow

---

## 5. Team Roles

| Role | Responsibility |
|------|---------------|
| **Security Analyst** | Audit imports, verify no backdoors in dead code, validate circuit breaker |
| **Developer** | Delete dead code, fix tests, harden eval gate |
| **DevOps Engineer** | Wire monitoring, create cron jobs, CI/CD pipeline health |
| **Architect** | Validate module boundaries, reduce coupling, document |
| **Tester** | Rewrite broken tests, add edge case coverage, regression test |
| **Product Owner** | Approve deletion scope, prioritize Phase 1-4, acceptance criteria |

---

## 6. fix_the_slop.md Alignment Matrix

| Principle | Current State | Gap | Phase |
|-----------|--------------|-----|-------|
| "Eval = generate→score→catch→fix" | Partially implemented | Gate not fully wired to integration | Phase 2 |
| "Threshold = 0.7" | Implemented in gate_check | Not enforced before file writes | Phase 2 |
| "Regression testing" | RegressionTracker exists | No baseline, not wired to workflow | Phase 2+4 |
| "Production monitoring" | ProductionMonitor exists | Not wired to cron or workflow | Phase 3 |
| "Feedback loop closes" | close_the_loop exists | Not called from any user flow | Phase 3 |
| "Quality benchmark: 3 parts" | Rubric + threshold | Missing gold standard cases | Phase 4 |
| "No silent failures" | Structured logging | Monitoring infrastructure orphaned | Phase 3 |
| "Score is a number" | Implemented | Retry loop doesn't use scores | Phase 2 |
