# Architect Action Plan

## Current Architecture Analysis

### What Exists
```
workflow.py          → LangGraph StateGraph with 8 sequential nodes
agentics.py          → AgenticsApp: service init, process_issue(), eval scoring
eval_rubric.py       → QualityRubric (4 criteria), score_output(), gate_check(), RubricStore
production_monitor.py→ ProductionMonitor, ThresholdAlerter, run_production_check(), close_the_loop()
state.py             → Single State TypedDict (good)
tools.py             → LangChain @tool functions
services.py          → ServiceManager, OllamaClient, GitHubClient, MCPClient
circuit_breaker.py   → Circuit Breaker, ServiceHealthMonitor, retry utilities
monitoring.py        → StructuredLogger, MetricsStore, WorkflowTracker, PerformanceMonitor
config.py            → AgenticsConfig (Pydantic), LLMConfig
models.py            → CodeSpec, TestSpecification, ValidationResults
exceptions.py        → 11 custom exception types
mcp_client.py        → MCP client with retry
```

### Critical Gaps (vs fix_the_slop.md requirements)

1. **Eval loop runs AFTER integration** — The `_node_generate_code_tests` integrates code into main.ts BEFORE the eval gate. If score < 0.7, the code is already integrated. This is "shipping defective units."

2. **No regression testing** — No saved baseline. No comparison of score delta. The system cannot detect "a change that fixes one thing and silently breaks three others."

3. **No saved test case suite** — No ground truth. No gold standard inputs/outputs. The eval rubric scores the current output but has nothing to regress against.

4. **Production monitoring is orphaned** — `ProductionMonitor` and `run_production_check()` exist but are never invoked. No cron, no scheduled sampling.

5. **Feedback loop is disconnected** — `close_the_loop()` exists but `record_feedback()` in `agentics.py` only matches by `issue_url` and calls `close_the_loop()`. No user-facing mechanism triggers this.

6. **Eval runs twice redundantly** — `score_output()` + `gate_check()` + `RubricStore().record()` runs in both `_node_generate_code_tests` AND `_node_test`. The second run overwrites the first.

7. **No threshold enforcement on integration** — Even when eval fails, the code is already written to main.ts. The gate is informational only.

8. **Structural integrity heuristic is weak** — The `structural_integrity` check gives +1 for every line that matches basic patterns, making it nearly impossible to score low. A file of garbage lines would score ~0.8.

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AgenticsApp.process_issue()               │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  Workflow     │    │  Eval Gate   │    │  Production  │   │
│  │  (LangGraph)  │───▶│  (Pre-ship)  │───▶│  Monitor     │   │
│  │              │    │              │    │  (Cron)      │   │
│  └──────────────┘    └──────┬───────┘    └──────────────┘   │
│                             │                                │
│                    ┌────────▼────────┐                       │
│                    │  RubricStore    │                       │
│                    │  (JSONL)        │                       │
│                    └────────┬────────┘                       │
│                             │                                │
│                    ┌────────▼────────┐                       │
│                    │  Feedback Loop  │                       │
│                    │  (close_the_loop)│                       │
│                    └─────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Module Redesign

### 1. `eval_rubric.py` — Enhanced
- **Add**: `RegressionTracker` class that loads baseline scores and computes deltas
- **Add**: `GoldStandardSuite` class for managing test cases (input → expected output)
- **Fix**: `structural_integrity` to use stricter heuristics (penalize long lines, missing semicolons, unbalanced parens)
- **Fix**: `requirement_coverage` to handle edge cases better (empty requirements → 0.0 not 0.5)

### 2. `workflow.py` — Restructured
- **Change**: Move eval gate BEFORE integration (generate → score → gate → integrate)
- **Add**: Regression check node that compares against baseline
- **Add**: `save_baseline()` / `load_baseline()` for score persistence
- **Fix**: Remove redundant eval in `_node_test` (keep only in `_node_generate_code_tests`)
- **Add**: Conditional routing — if eval fails, route to retry node instead of continuing

### 3. `agentics.py` — Enhanced
- **Add**: `run_regression_suite()` method that loads gold standard cases and scores them
- **Add**: `schedule_production_monitoring()` guidance for cron setup
- **Fix**: `record_feedback()` to properly validate feedback dict before calling `close_the_loop()`

### 4. `production_monitor.py` — Wired Up
- **Add**: `ProductionScheduler` class for cron-compatible periodic checks
- **Add**: Alert delivery mechanism (not just return string)
- **Fix**: `run_production_check()` to return structured dict instead of string

### 5. New: `test_suite.py` — Gold Standard Management
- **Create**: `GoldStandardSuite` class with CRUD for test cases
- **Create**: JSON file format for storing gold standard cases
- **Create**: CLI-compatible functions for adding/removing cases

### 6. New: `regression.py` — Regression Testing
- **Create**: `RegressionTracker` class
- **Create**: Baseline save/load (JSON)
- **Create**: Score delta computation and threshold checking

## Data Flow (Target)

```
1. fetch_issue → clarify_ticket → plan_implementation → extract_code
2. generate_code_tests (LLM generates code + tests)
3. EVAL GATE:
   a. score_output() → 4 criteria scores
   b. gate_check() → pass/fail
   c. If fail → record_failure() → feed back to LLM (retry, max 3)
   d. If pass → continue
4. integrate_code (only if eval passed)
5. test (run jest, record metrics)
6. output
7. POST-INTEGRATION:
   a. Regression check: compare scores against baseline
   b. Update baseline if improved
   c. Log to RubricStore
```

## File Changes

| File | Change Type | Description |
|------|------------|-------------|
| `eval_rubric.py` | Enhance | Fix structural_integrity, add RegressionTracker |
| `workflow.py` | Restructure | Move eval gate before integration, add conditional routing |
| `agentics.py` | Enhance | Add regression suite runner, fix feedback loop |
| `production_monitor.py` | Enhance | Add scheduler, structured output |
| `test_suite.py` | Create | Gold standard test case management |
| `regression.py` | Create | Regression testing with baseline comparison |
| `state.py` | Minor | Add regression_score, baseline_score fields |
| `tools.py` | Minor | Add eval-specific tools |

## Integration Points

1. **Eval Gate → Workflow**: Conditional edge in StateGraph (pass→integrate, fail→retry)
2. **RubricStore → Production Monitor**: Shared JSONL file
3. **Feedback Loop → RubricStore**: `close_the_loop()` writes flagged entries
4. **Regression → Eval**: `RegressionTracker` reads RubricStore history

## Constraints

- All changes scoped to `agents/agentics/`
- No changes to `src/` (Obsidian plugin)
- No changes to `dagger-pipeline/`
- Must maintain backward compatibility with existing 104 tests
- Must use existing `State` TypedDict (extend, don't replace)
