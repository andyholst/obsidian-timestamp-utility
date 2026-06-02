# Architect — Action Plan

## Objective
Validate and simplify module boundaries, reduce coupling, ensure the architecture aligns with fix_the_slop.md quality principles, and document the target architecture.

## Tasks

### ARC-01: Module Boundary Audit

**Current state**: 49 source files, 8 live, 41 dead, unclear boundaries.

**Target state**: ~15 source files with clear single responsibilities.

**Target module structure**:
```
src/
├── __init__.py          → Package exports (AgenticsApp, State)
├── config.py            → Configuration (AgenticsConfig, LLMConfig) [KEEP]
├── state.py             → Single State TypedDict [KEEP]
├── eval_rubric.py       → Quality scoring + RegressionTracker + RubricStore [KEEP]
├── test_suite.py        → GoldStandardSuite [KEEP]
├── production_monitor.py→ Production monitoring + feedback loop [KEEP]
├── workflow.py          → LangGraph workflow [KEEP]
├── agentics.py          → Application entry point [KEEP]
├── circuit_breaker.py   → Circuit breaker + health monitor [KEEP]
├── monitoring.py        → Structured logging [KEEP - but simplify]
├── utils.py             → Utility functions [KEEP]
├── services.py          → Service management [KEEP]
├── test_suite.py        → GoldStandardSuite [KEEP]
├── exceptions.py        → Custom exceptions [KEEP]
├── mcp_client.py        → MCP client [KEEP]
```

**Action**: Verify this is the complete set after dead code deletion. No additional files should remain.

### ARC-02: Reduce Coupling in Services

**Current issue**: `services.py` initializes 4 services (ollama_reasoning, ollama_code, github, mcp) but the workflow only needs 3 (ollama_reasoning, ollama_code, github). MCP is optional.

**Fix**: Make MCP truly optional:
```python
# In AgenticsApp.initialize():
self.service_manager.mcp = None  # Don't initialize MCP by default
```

### ARC-03: Simplify Monitoring

**Current issue**: `monitoring.py` has 456 lines with `MetricsStore`, `PerformanceMonitor`, `WorkflowTracker`, `time_execution` decorator — none of which are wired into the workflow.

**Fix**: Reduce to the essentials:
- `StructuredLogger` — KEEP (used by eval_rubric, production_monitor)
- `structured_log()` — KEEP (factory function)
- `MetricsStore` — DELETE (never instantiated)
- `PerformanceMonitor` — DELETE (never instantiated)
- `WorkflowTracker` — DELETE (never instantiated)
- `time_execution` — DELETE (never used)
- `track_agent_execution` — DELETE (never used)
- `track_workflow_progress` — DELETE (never used)

**Reduction**: 456 → ~200 lines.

### ARC-04: Circuit Breaker Consistency

**Current issue**: `config.py` has duplicate circuit breaker settings:
- `circuit_breaker_failure_threshold: int = 3`
- `circuit_breaker_recovery_timeout: int = 30`
- `github_circuit_breaker_failure_threshold: int = 5`
- `github_circuit_breaker_recovery_timeout: int = 60`

But `GitHubClient` uses hardcoded values in `get_repo()`/`get_user()` instead of reading from config.

**Fix**: Pass config values to service clients at initialization.

### ARC-05: State TypedDict Completeness

**Current issue**: `state.py` has 25+ fields but only ~8 are used by any node. Many are remnants of the old agent architecture.

**Target State fields** (only what's needed):
```python
class State(TypedDict, total=False):
    # Core
    url: str
    ticket_content: str
    refined_ticket: dict
    
    # Generated
    generated_code: str
    generated_tests: str
    method_name: str
    command_id: str
    
    # Context
    relevant_code_files: list
    relevant_test_files: list
    
    # Metrics
    existing_tests_passed: int
    post_integration_tests_passed: int
    
    # Recovery
    validation_score: int
    recovery_attempt: int
    
    # Errors
    error: str
    error_type: str
    success: bool
    
    # Eval loop
    eval_scores: dict
    eval_passed: bool
    eval_reasons: list
    failed_criteria: list
    
    # Regression
    regression_check: dict
    
    # Integration gate
    integrated: bool
    integration_blocked_reason: str
    result: dict
```

### ARC-06: Document Target Architecture

Create `docs/devsecops/ARCHITECTURE_TARGET.md` with:
- Module dependency diagram
- Data flow diagram
- Interface contracts between modules
- Quality checkpoint diagram (where fix_the_slop.md principles are enforced)

## Deliverables
- ARC-01: Module boundary verification (pass after deletion)
- ARC-02: MCP made optional in services.py
- ARC-03: monitoring.py reduced to ~200 lines
- ARC-04: Circuit breaker config passed to clients
- ARC-05: State TypedDict trimmed to required fields only
- ARC-06: Target architecture document

## Sign-off Criteria
- `find agents/agentics/src -name "*.py" -not -name "__init__.py" | wc -l` ≤ 15
- No circular imports
- Each module has a single clear responsibility
- Architecture document reviewed by team
