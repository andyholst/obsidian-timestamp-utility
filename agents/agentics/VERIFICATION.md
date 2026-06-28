# VERIFICATION.md — Agentic Loop Protocol

## Purpose

Defines the closed-loop verification contract for every node in the LangGraph agent pipeline.
Each node MUST verify its output before passing control downstream. On failure, the node retries
with error feedback up to `max_attempts`. On exhaustion, control routes to recovery/skip.

This is the agentic equivalent of the build→run→verify→fix loop in AGENTS.md.

---

## Universal Node Contract

Every graph node follows this protocol:

```
1. EXECUTE  → Run the node's core logic (LLM call, tool call, etc.)
2. VERIFY   → Check output against acceptance criteria
3. PASS     → Return state → next node
4. FAIL     → Feed error context back → retry same node (attempt += 1)
5. EXHAUST  → Max attempts reached → route to recovery/skip
```

### Standard State Fields (State TypedDict)

| Field | Type | Description |
|-------|------|-------------|
| `recovery_attempt` | `int` | Current retry count (0 = first attempt) |
| `validation_score` | `int` | Last verification score (0-100) |
| `error` | `str` | Error message from last failure |
| `error_type` | `str` | Error classification |
| `eval_passed` | `bool` | Whether eval gate passed |
| `eval_scores` | `dict` | Detailed eval scores |
| `failed_criteria` | `list` | Which criteria failed |
| `integrated` | `bool` | Whether code was integrated |

### Standard Env Vars

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MAX_RETRIES` | `3` | Universal max retry attempts per node |
| `AGENT_RETRY_THRESHOLD` | `80` | Minimum score to consider verification passed |
| `AGENT_VERIFY_ENABLED` | `true` | Master switch for verification loops |
| `AGENT_FAST_MODE` | `false` | Skip retries, single-pass mode (for tests) |

---

## Per-Node Acceptance Criteria

### 1. fetch_issue

| Criterion | Check | Failure Action |
|-----------|-------|----------------|
| Ticket content non-empty | `len(ticket_content) > 0` | Retry with error context |

### 2. clarify_ticket

| Criterion | Check | Failure Action |
|-----------|-------|----------------|
| Requirements extracted | `len(requirements) > 0` | Use default ticket |
| Acceptance criteria present | `len(acceptance_criteria) > 0` | Use default ticket |

### 3. generate_code_tests

| Criterion | Check | Failure Action |
|-----------|-------|----------------|
| Code generated | `len(generated_code) > 0` | Retry with error context |
| Code has valid syntax | No class, has export function | Retry with validation errors |
| Tests generated | `len(generated_tests) > 0` | Use fallback tests |
| Tests pass | Jest exit code 0 | Retry with test errors (up to 3x) |
| Eval gate passed | `eval_passed == True` | Retry with eval feedback (up to 3x) |

### 4. test (post-integration)

| Criterion | Check | Failure Action |
|-----------|-------|----------------|
| Tests execute | Jest returns exit code | Report failure |
| No regressions | `tests_passed == True` | Flag for review |

---

## Loop Termination Conditions

A node's retry loop terminates when ANY of:
1. **Verification passes** → proceed to next node
2. **`recovery_attempt >= AGENT_MAX_RETRIES`** → route to recovery/skip
3. **`AGENT_VERIFY_ENABLED=false`** → single-pass mode (tests)
4. **`AGENT_FAST_MODE=true`** → skip verification entirely (ultra-fast tests)

---

## Graph Topology with Verification

```
fetch_issue → clarify_ticket → plan_implementation → extract_code → generate_code_tests
                                                                        │
                                              ┌─────────────────────────┤
                                              │ eval_passed?            │
                                              │                         ▼
                                              │                    [retry] ← up to 3x
                                              │                         │
                                              ▼                         ▼
                                             test ──────────────────→ output
```

---

## Implementation Mapping

| File | Responsibility |
|------|---------------|
| `src/loop_engineering.py` | `verify_and_retry()` wrapper, `VerificationResult`, per-node verify functions |
| `src/workflow.py` | Graph wiring with conditional edges per node, uses `verify_and_retry` |
| `src/eval_rubric.py` | Eval scoring/gating (already exists) |
| `VERIFICATION.md` (this file) | Acceptance criteria source of truth |
