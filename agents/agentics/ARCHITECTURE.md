# Agentic Code Generation — Architecture

## 1. System Overview

The `agents/agentics/` Python package implements a **LangGraph-based autonomous code generation pipeline**. It takes a GitHub issue URL as input, generates TypeScript code and Jest tests for an Obsidian plugin, integrates them into the existing codebase, and validates output quality through a multi-criterion **eval loop** with a self-correction retry mechanism.

```
Input: GitHub Issue URL
  → Fetch issue body
  → LLM extracts structured requirements (JSON)
  → Plan implementation (ensure required fields)
  → Extract existing code from disk
  → Generate .ts module + tests (with eval gate)
  → Integrate into main.ts if eval passes
  → Run full Jest suite
  → Output success/failure with quality scores
Output: Generated .ts module + tests, integrated or blocked
```

## 2. Architecture Diagram

```
┌──────────────┐     ┌────────────────┐     ┌────────────────────┐     ┌──────────────┐
│ fetch_issue  │────▶│ clarify_ticket │────▶│ plan_implementation│────▶│ extract_code │
│  (PyGithub)  │     │  (LLM → JSON)  │     │   (passthrough)    │     │  (filesystem)│
└──────────────┘     └────────────────┘     └────────────────────┘     └──────┬───────┘
                                                                              │
                    ┌─────────────────────────────────────────────────────────┘
                    ▼
     ┌──────────────────────────────────────────────────────────────────────────────┐
     │                        generate_code_tests (CORE NODE)                        │
     │                                                                              │
     │  ┌─────────────────────────────────────────────────────────────────────────┐ │
     │  │ Sub-steps:                                                              │ │
     │  │  a. LLM-aided naming → export_name, command_id                         │ │
     │  │  b. Generate TS module code (up to 3 attempts, syntax validation)      │ │
     │  │  c. Generate Jest tests (LLM or fallback template)                     │ │
     │  │  d. Run generated tests, self-correct on failure (3 attempts)          │ │
     │  │  e. EVAL GATE: score_output → gate_check                               │ │
     │  │     ├── PASS → proceed to integration                                  │ │
     │  │     └── FAIL → block integration, set eval_failure_context             │ │
     │  │  f. (if passed) Write import+addCommand into main.ts,                  │ │
     │  │     write tests to separate file, append integration tests             │ │
     │  │  g. Regression check & baseline save                                   │ │
     │  └─────────────────────────────────────────────────────────────────────────┘ │
     └──────────────────────────────────────────────────────────────────────────────┘
                    │
                    │  _route_after_generate
                    ├── eval_passed ──────────────▶ test
                    ├── retry < 3 ────────────────▶ generate_code_tests (loop)
                    └── max retries ──────────────▶ output (skip test, integrated=False)
                                                         │
                    ┌────────────────────────────────────┘
                    ▼
     ┌──────────┐     ┌──────────┐
     │   test   │────▶│  output  │──▶ END
     │(Jest all)│     │(result)  │
     └──────────┘     └──────────┘

RETRY LOOP:
┌─────────────────────────────────────────────────────────────────┐
│  generate_code_tests                                            │
│    │ eval fails, recovery_attempt < 3                          │
│    │ state["recovery_attempt"] += 1                            │
│    │ state["eval_failure_context"] = "what failed + fix hints"  │
│    ▼                                                           │
│  generate_code_tests (again — uses eval_failure_context prompt) │
└─────────────────────────────────────────────────────────────────┘
```

**Routing logic** in `_route_after_generate(state: State) → str`:

| Condition | Route to | Meaning |
|---|---|---|
| `state["eval_passed"] == True` | `"test"` | Eval gate passed — run full Jest suite |
| `state["recovery_attempt"] >= 3` | `"output"` | Max retries exhausted — output failure |
| Otherwise | `"generate_code_tests"` | Loop back for another attempt |

## 3. LangGraph StateGraph

Built in `AgenticsWorkflow._build_workflow()`, compiled with `MemorySaver` for checkpointing.

### Node Descriptions

| Node | Inputs (from State) | Outputs (to State) | Behavior |
|---|---|---|---|
| **fetch_issue** | `url` | `ticket_content`, `error` | Parses URL to extract owner/repo/issue#, queries GitHub API via PyGithub, stores issue body |
| **clarify_ticket** | `ticket_content` | `refined_ticket` | Sends issue text to reasoning LLM, extracts structured JSON: `{title, description, requirements[], acceptance_criteria[], implementation_steps[], ...}`. Falls back to defaults if LLM fails |
| **plan_implementation** | `refined_ticket` | `refined_ticket` (ensured) | Passthrough that guarantees all required fields exist (`implementation_steps`, `npm_packages`, `manual_implementation_notes`) |
| **extract_code** | — | `relevant_code_files[]`, `relevant_test_files[]` | Reads `src/main.ts` and `src/__tests__/main.test.ts` from disk into state as `[{file_path, content}]` lists |
| **generate_code_tests** | `refined_ticket`, `ticket_content`, `relevant_code_files` | `generated_code`, `generated_tests`, `method_name`, `command_id`, `eval_scores`, `eval_passed`, `integrated`, `eval_failure_context`, `regression_check` | **The core node** (see §4). Generates .ts module + Jest tests, runs eval gate, integrates into codebase if passed |
| **test** | — | `post_integration_tests_passed`, `existing_tests_passed` | Runs `npx jest --no-cache --testPathPattern src/__tests__/` against the full test suite post-integration |
| **output** | `integrated`, `generated_code`, `generated_tests`, `eval_scores`, `eval_passed` | `success`, `result` | Sets final `success=True` if `integrated==True`, else `False`. Builds structured result dict |

### Edges

```
fetch_issue ──▶ clarify_ticket ──▶ plan_implementation ──▶ extract_code ──▶ generate_code_tests
                                                                               │
                                                        ┌──────────────────────┤
                                                        │  (conditional)       │
                                                        ▼                      ▼
                                                     [test]              [generate_code_tests]
                                                        │                      │
                                                        ▼                      │
                                                     [output] ──▶ END ◀────────┘ (via retry loop)
```

## 4. The `generate_code_tests` Node (Detailed)

This is the most complex node (~350 lines). It orchestrates code generation, test generation, eval gating, and file integration.

### Sub-Steps

#### (a) Derive Export Name and Command ID

```python
slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40]
export_name = slug.split('-')[0] + ''.join(p.title() for p in slug.split('-')[1:])
command_id = slug
```

On the **first attempt** (not eval retries), the reasoning LLM refines these names:
```
Prompt: "Given this GitHub issue, propose: 1. camelCase function name 2. kebab-case command id"
Output: {"export_name": "generateUuidV7", "command_id": "insert-uuid-v7"}
```
Both LLM-proposed names are validated against regex: `^[a-z][a-zA-Z0-9]+$` / `^[a-z][a-z0-9-]+$`.

#### (b) Generate TypeScript Module Code

Up to **3 attempts** with syntax validation:

1. **Build prompt** via `_build_module_prompt()` — includes issue title, requirements, and the export name constraint
2. **LLM code model** generates code
3. **Post-processing** (`_post_process_generated_code`): strip imports, fix hex underscores (`0x1234_5678`), squash blank lines
4. **Validation gate** (`_is_valid_ts_syntax`):
   - Balanced `{}` and `()`
   - No `const` reassignment patterns (`const x = 5; x = 10`)
   - No `class` declarations, no `import` statements
   - Must contain `export function {export_name}` or `export { export_name }`
5. If validation fails → feed errors back, retry
6. On final attempt → write to `src/generated/{slug}.ts`

On **eval retries**, the first attempt uses `_build_eval_retry_prompt()` which includes `eval_failure_context` feedback.

#### (c) Generate Jest Tests

1. **LLM prompt**: "Write Jest tests for this TS module. Import `{export_name}` from '../../generated/{slug}'. Include describe, 'should be a function', 'should return a string'."
2. **Fallback** (`_fallback_tests`): If LLM output is empty or missing `describe(`, generate minimal template tests:
   ```typescript
   import { exportName } from '../../generated/slug';
   describe('exportName', () => {
       it('should be a function', () => { ... });
       it('should return a string', () => { ... });
   });
   ```
3. Write to `src/__tests__/generated/{slug}.test.ts`

#### (d) Run Generated Tests + Self-Correct

Up to **3 validation attempts**:

1. Run `npx jest --no-cache {gen_test_file}` in `PROJECT_ROOT` with `NODE_ENV=development`
2. If pass → proceed to eval gate
3. If fail → extract error lines (lines starting with `●`, `TypeError`, `Error:`, `FAIL`), feed back to LLM to regenerate **both code and tests**
4. On final attempt failure → `gen_test_code = ""` (so eval gate will block)

#### (e) Eval Gate

```python
state["generated_code"] = gen_code
state["generated_tests"] = gen_test_code
state["tests_passed"] = (tres.returncode == 0)
ev = score_output(state)       # returns {scores, total, passed, threshold, reasons}
passed, gate_reason = gate_check(ev)
```

If eval **fails**:
- `state["integrated"] = False`
- `state["eval_failure_context"]` = human-readable string: "Score: 0.45/1.0. Failed criteria: structural_integrity. What was wrong: structural_integrity=0.00. What to fix: Fix syntax errors..."
- `state["recovery_attempt"] = 0` (reset for retry loop)
- Regression check still runs, but no baseline save
- Returns state early (no integration)

If eval **passes**:
- `state["integrated"] = True`
- `state["eval_failure_context"] = ""`
- Proceeds to integration

#### (f) Integration (Eval Passed Only)

1. **Backup** `src/main.ts` to `src/.agentics_backups/main.ts.{timestamp}.bak`
2. **Add import**: `import { exportName } from './generated/slug';` after the last existing import line
3. **Add command**: Insert `this.addCommand({...})` block inside `onload()` via `_find_onload_insert_point()`
4. **Write tests**: Save generated tests to `src/__tests__/generated/{slug}.test.ts`
5. **Append integration tests**: `_build_integration_tests()` creates tests that verify the command is registered with correct id/name/editorCallback, uses mock objects (no Obsidian import needed). Appended to `src/__tests__/main.test.ts` before final `});`

#### (g) Regression Check + Baseline Save

```python
tracker = RegressionTracker()
state["regression_check"] = tracker.check_regression(ev)  # compare vs saved baseline
tracker.save_baseline(ev)  # save as new baseline (always on success)
state["validation_score"] = 100 if (gen_code and gen_test_code) else 0
```

## 5. Eval Loop / Quality Gate

### File: `src/eval_rubric.py`

### 7 Weighted Criteria

| Criterion | Weight | What It Measures |
|---|---|---|
| `has_actionable_output` | 0.15 | Is `generated_code` non-empty? `1.0` if yes, `0.0` if no |
| `compiles_successfully` | 0.25 | Runs `npx tsc --noEmit` on generated code. Returns `0.5` (neutral) if `PROJECT_ROOT` is missing — **NOT a hard gate** |
| `tests_pass` | 0.20 | `1.0` if `state["tests_passed"]` is True, `0.5` if tests exist but unknown, `0.0` if no tests |
| `test_quality` | 0.20 | 5 sub-checks: calls generated function (0.5+0.5), checks return type is string (1.0), checks format/length (1.0), checks uniqueness (1.0), has ≥3 `it()` blocks (1.0). Scored as `achieved/max` |
| `structural_integrity` | 0.10 | Balanced braces + parens are **hard gates** (cap at 0.4). Line syntax validation: recognizes `function`, `const/let/var`, `return`, braces/semicolons, `import`, `describe/it/test`, `expect/assert`, etc. Penalizes lines >200 chars |
| `requirement_coverage` | 0.05 | Fraction of non-stopword keywords from `refined_ticket.requirements` found in `code + tests`. Returns `0.0` for empty requirements |
| `test_validation` | 0.05 | If counts available: `passed/total`. Otherwise heuristic: ratio of `assert/expect/test/it/describe` lines to total test lines. `0.5` neutral if no tests |

### Hard Gates

1. **Code-test consistency** (`_check_code_test_consistency`): Test imports must match code exports. If test imports `foo` but code only exports `bar` → **HARD FAIL** (total = 0.0).
2. **Tests pass == 0.0**: If no tests were generated (`generated_tests` is empty) and `tests_passed` is not set to True → **HARD FAIL** (total = 0.0). Note: when tests exist but fail, `tests_pass()` returns 0.5 (partial credit), so this hard gate only triggers when no test code was produced.
3. `compiles_successfully` is **NOT a hard gate**. When `PROJECT_ROOT` is absent (e.g., in Dagger), it returns `0.5` neutral. Syntax errors are caught by `_is_valid_ts_syntax` in the inner generation loop before eval.

### Score Calculation

```python
total = sum(scores[criterion] * WEIGHTS[criterion] for criterion in WEIGHTS)
passed = total >= threshold  # default threshold = 0.7
```

### `score_output(state) → dict`

Returns `{scores, total, passed, threshold, reasons}`. If any hard gate triggers, total is forced to 0.0. Otherwise computes weighted sum and lists worst-performing criteria as reasons.

### `gate_check(score_result) → (bool, str)`

Simple threshold check: `total >= threshold`. Returns `(False, reason_string)` on failure.

### `record_failure(state, score_result) → dict`

Produces structured failure context for retries:
```python
{
    "failed_criteria": ["structural_integrity", "test_quality"],
    "what_was_wrong": ["structural_integrity=0.00", "test_quality=0.20"],
    "what_to_fix": ["Fix syntax errors: balanced braces, correct TypeScript syntax.", ...],
    "scores": {...},
    "total": 0.45,
    "threshold": 0.7
}
```

### `RegressionTracker`

- **Save baseline**: Writes `{timestamp, scores, total}` to `/tmp/eval_baseline.json`
- **Load baseline**: Returns saved baseline or None
- **Check regression**: Compares current scores against baseline — flags `regressed=True` if any criterion drops > 0.1
- **Save if improved**: Only overwrites baseline if current score >= previous

### `RubricStore`

JSONL append-only store at `EVAL_STORE_PATH` (default `/tmp/eval_results.jsonl`):
```jsonl
{"timestamp":"2026-06-02T...","total":0.85,"passed":true,"scores":{...},"issue_url":"..."}
```
Methods: `record()`, `get_history(n)`, `_read_all()`

### Self-Correction via `eval_failure_context`

When the eval gate fails, the node constructs a detailed context string:
```
"Score: 0.45/1.0 (threshold: 0.7). Failed criteria: structural_integrity, test_quality.
 What was wrong: structural_integrity=0.00, test_quality=0.20.
 What to fix: Fix syntax errors: balanced braces, correct TypeScript syntax.; ..."
```

This is fed back to the LLM in `_build_eval_retry_prompt()` on the next loop iteration.

## 6. State TypedDict

Defined in `src/state.py`:

| Field | Type | Purpose |
|---|---|---|
| `url` | `str` | GitHub issue URL (entry point) |
| `ticket_content` | `str` | Raw issue body from GitHub API |
| `refined_ticket` | `dict` | Structured JSON extracted by LLM: `{title, description, requirements[], acceptance_criteria[], implementation_steps[], npm_packages[], affected_files[], full_original_content}` |
| `result` | `dict` | Final output: `{code_generated, tests_generated, method_name, eval_scores, eval_passed, integrated, integration_blocked_reason, regression_check}` |
| `generated_code` | `str` | Generated TypeScript module source |
| `generated_tests` | `str` | Generated Jest test source |
| `method_name` | `str` | camelCase export function name (e.g., `generateUuidV7`) |
| `command_id` | `str` | kebab-case Obsidian command ID (e.g., `insert-uuid-v7`) |
| `relevant_code_files` | `List[Dict[str,str]]` | `[{file_path, content}]` — contents of `src/main.ts` |
| `relevant_test_files` | `List[Dict[str,str]]` | `[{file_path, content}]` — contents of `src/__tests__/main.test.ts` |
| `existing_tests_passed` | `int` | Count from post-integration test run |
| `post_integration_tests_passed` | `int` | Count from post-integration test run |
| `tests_passed` | `bool` | Whether generated tests passed (set by `generate_code_tests` node) |
| `validation_score` | `int` | `100` if code+tests generated, `0` otherwise |
| `recovery_attempt` | `int` | Retry counter (incremented by `_route_after_generate`) |
| `error` | `str` | Error message from any node (e.g., GitHub API failure) |
| `error_type` | `str` | Exception class name |
| `success` | `bool` | Final success flag (set by `output` node) |
| `eval_scores` | `dict` | Per-criterion scores from `score_output()` |
| `eval_passed` | `bool` | Did eval gate pass? |
| `eval_reasons` | `List[str]` | Reasons if eval failed |
| `failed_criteria` | `List[str]` | Criteria that scored < 0.7 |
| `regression_check` | `dict` | `{has_baseline, regressed, deltas, total_delta, baseline_total, current_total}` |
| `integrated` | `bool` | Was code integrated into main.ts? |
| `integration_blocked_reason` | `str` | Why integration was blocked (eval gate reason) |
| `eval_failure_context` | `str` | Human-readable failure feedback for LLM retry |

## 7. Module Map

| File | Key Classes/Functions | Role |
|---|---|---|
| **agentics.py** | `AgenticsApp` | Entry point. Initializes services, creates `AgenticsWorkflow`, exposes `process_issue(url)`, `get_quality_report()`, `record_feedback()`, `run_regression_suite()`, `shutdown()` |
| **workflow.py** | `AgenticsWorkflow` | LangGraph `StateGraph` definition, all 7 node methods (`_node_*`), helper functions for code/test insertion, prompt builders, routing logic |
| **state.py** | `State(TypedDict)` | Single TypedDict for entire workflow (26 fields) |
| **config.py** | `AgenticsConfig`, `LLMConfig`, `init_config()`, `setup_logging()` | Pydantic + dataclass config. Reads env vars: `GITHUB_TOKEN`, `OLLAMA_HOST`, `OLLAMA_REASONING_MODEL`, `OLLAMA_CODE_MODEL`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT` |
| **services.py** | `ServiceManager`, `OllamaClient`, `GitHubClient`, `MCPClient`, `ServiceClient(ABC)` | External service clients with circuit breaker integration, lazy initialization, health checks |
| **eval_rubric.py** | `QualityRubric`, `score_output()`, `gate_check()`, `record_failure()`, `RegressionTracker`, `RubricStore` | 7-criterion quality evaluation, hard gates, regression detection, score persistence |
| **circuit_breaker.py** | `CircuitBreaker`, `ServiceHealthMonitor`, `exponential_backoff()`, `retry_with_backoff()` | Circuit breaker pattern (CLOSED→OPEN→HALF_OPEN), retry decorators with jittered exponential backoff |
| **monitoring.py** | `StructuredLogger`, `structured_log()`, `record_circuit_breaker_state()` | JSON-formatted structured logging |
| **production_monitor.py** | `ProductionMonitor`, `ThresholdAlerter`, `run_production_check()`, `close_the_loop()` | Continuous quality monitoring: degradation detection (>10% drop), trend analysis, alerting |
| **mcp_client.py** | `MCPClient` (low-level, aiohttp-based) | Direct MCP bridge HTTP client for context7 and memory servers. Uses `tenacity` retries |
| **test_suite.py** | `GoldStandardSuite` | Gold standard test case management: `add_case()`, `get_case()`, `get_all_cases()`, `remove_case()`. Input→expected output pairs with per-criterion thresholds |
| **utils.py** | `validate_github_url()`, `remove_thinking_tags()`, `log_info()` | GitHub URL validation (regex), LLM output cleaning (think tags, code fences), structured logging helper |
| **exceptions.py** | `AgenticsError`, `ConfigurationError`, `ServiceUnavailableError`, `ValidationError`, `GitHubError`, `OllamaError`, `MCPError`, `WorkflowError`, `CircuitBreakerError`, `HealthCheckError`, `BatchProcessingError` | Exception hierarchy. All custom exceptions inherit from `AgenticsError` |

## 8. File System Layout

### Reads

| Path | When | Purpose |
|---|---|---|
| `src/main.ts` | `extract_code` node | Read existing plugin code for context |
| `src/__tests__/main.test.ts` | `extract_code` node | Read existing tests, strip old LLM-generated blocks |

### Writes

| Path | When | Content |
|---|---|---|
| `src/generated/{slug}.ts` | `generate_code_tests` (code gen) | Generated TypeScript module with `export function` |
| `src/__tests__/generated/{slug}.test.ts` | `generate_code_tests` (test gen) | Generated Jest tests for the module |

### Modifies

| Path | When | What Changes |
|---|---|---|
| `src/main.ts` | `generate_code_tests` (integration) | **Adds** `import { exportName } from './generated/slug';` after last import. **Inserts** `this.addCommand({...})` block inside `onload()` |
| `src/__tests__/main.test.ts` | `generate_code_tests` (integration) | **Appends** integration test `describe` block before final `});` |

### Backups

| Path | Pattern |
|---|---|
| `src/.agentics_backups/main.ts.{timestamp}.bak` | Timestamped copy before modification |

### Directories Created

- `src/generated/` — generated .ts modules
- `src/__tests__/generated/` — generated test files
- `src/.agentics_backups/` — pre-modification backups

## 9. Export-Based Architecture

Generated code lives as **standalone `.ts` modules** in `src/generated/`, not as class methods injected into `TimestampPlugin`.

```
src/generated/
├── insert-uuid-v7.ts          # export function generateUuidV7(): string { ... }
├── insert-timestamp-link.ts   # export function insertTimestampLink(): string { ... }
└── ...

src/main.ts:
  import { generateUuidV7 } from './generated/insert-uuid-v7';
  import { insertTimestampLink } from './generated/insert-timestamp-link';
  // ...
  async onload() {
      this.addCommand({
          id: 'insert-uuid-v7',
          name: 'Insert UUID v7',
          editorCallback: (editor, _ctx) => {
              editor.replaceSelection(generateUuidV7());
          },
      });
  }
```

**Key principles**:
- Each generated module exports a single function: `export function name(): string`
- No class declarations, no imports (uses browser/Node built-ins only)
- `main.ts` imports the function and wraps it in an `addCommand` call
- Integration tests verify command registration + callback behavior with mock objects (no Obsidian import needed)

## 10. Configuration

| Env Variable | Default | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | *(required)* | GitHub API authentication token |
| `OLLAMA_REASONING_MODEL` | `sorc/qwen3.5-claude-4.6-opus:9b` | Model for reasoning tasks (ticket clarification, naming) |
| `OLLAMA_CODE_MODEL` | `sorc/qwen3.5-claude-4.6-opus:9b` | Model for code/test generation |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_NUM_CTX` | `8192` | Context window size for code model |
| `OLLAMA_NUM_PREDICT` | `2048` | Max tokens for code model |
| `PROJECT_ROOT` | current working directory | Path to Obsidian plugin repo root (needed for file I/O and `tsc`/`jest`) |
| `EVAL_THRESHOLD` | `0.7` | Minimum weighted score to pass the eval gate |
| `EVAL_STORE_PATH` | `/tmp/eval_results.jsonl` | RubricStore persistence path |
| `MCP_SERVER_URL` | `http://mcp:3003` | MCP bridge URL |

**LLMConfig** (dataclass) holds runtime parameters: `temperature=0.7`, `top_p=0.7`, `top_k=20`, `min_p=0.0`, `presence_penalty=1.5`, `num_ctx=4096` (reasoning) / configurable (code), `num_predict=1024` (reasoning) / configurable (code).

## 11. Test Strategy

### Unit Tests (`tests/unit/`)

**Fast, mocked** — no Ollama, no GitHub API:

| File | Tests | What It Covers |
|---|---|---|
| `test_workflow_unit.py` | 44 | Node-by-node testing with mocked LLM/GitHub clients. Verifies parameter passing, error handling, state mutations |
| `test_workflow_edge_cases.py` | 17 | Empty inputs, LLM failures, GitHub API failures, state preservation, routing decisions |
| `test_state_unit.py` | 4 | State TypedDict schema validation |
| `test_config_unit.py` | — | Config validation (Pydantic model) |
| `test_exceptions_unit.py` | 55 | Exception hierarchy — proper inheritance, message propagation |
| `test_eval_rubric_enhanced.py` | — | Eval rubric scoring correctness |
| `test_eval_gate_integration.py` | — | Eval gate integration with state |
| `test_workflow_integration.py` | — | Workflow node orchestration |
| `test_circuit_breaker.py` | — | Circuit breaker state transitions |
| `test_test_suite.py` | — | Gold standard suite CRUD |
| `test_regression.py` | — | RegressionTracker check/save |
| `test_production_monitor_enhanced.py` | — | Production monitoring + alerting |

### Integration Tests (`tests/integration/`)

**Real Ollama + GitHub API** (requires `GITHUB_TOKEN` and running Ollama):

| File | What It Tests |
|---|---|
| `test_ticket20_e2e_integration.py` | End-to-end flow for issue #20 with real LLM generation |
| `test_ticket22_e2e_integration.py` | End-to-end flow for issue #22 with real LLM generation |

### Eval Gate Tests

Implemented within `tests/unit/test_eval_rubric_enhanced.py` and `tests/unit/test_eval_gate_integration.py`:
- Tests all 7 criteria scoring independently
- Tests hard gates: code-test inconsistency, tests_pass == 0.0
- Tests regression detection with different baseline states
- Tests RubricStore append/read cycle

### Make Targets

```bash
make test-agents-unit-mock    # Mocked unit tests (fast)
make test-agents-integration  # Integration tests (needs Ollama + GitHub)
make test-agents              # All agent tests
make run-agentics ISSUE_URL=  # Full workflow with real services
```
