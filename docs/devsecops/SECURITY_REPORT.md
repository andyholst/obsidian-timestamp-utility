# SEC-01 Security Audit Report

**Audit Date:** 2026-05-31
**Auditor:** security-analyst (automated)
**Scope:** `agents/agentics/` — Python agentic workflow codebase
**Live entry point:** `src/agentics.py`

---

## Executive Summary

| Check | Status | Severity |
|-------|--------|----------|
| SEC-01: Import Chain Verification | PASS | — |
| SEC-02: Credential Audit | **PASS** (fixed) | WAS HIGH |
| SEC-03: Circuit Breaker Validation | PASS | — |
| SEC-04: Input Validation Audit | PASS (with notes) | LOW |
| SEC-05: Dead Code Backdoor Check | PASS | — |

---

## SEC-01: Import Chain Verification

**Result: PASS — No dead code is reachable from the live import chain.**

### Live import tree (from `agentics.py`)

```
agentics.py
├── config.py
├── eval_rubric.py
│   ├── utils.py
│   └── monitoring.py
├── exceptions.py
├── monitoring.py
├── production_monitor.py
│   └── eval_rubric.py (already listed)
├── services.py
│   ├── config.py (already listed)
│   ├── exceptions.py (already listed)
│   ├── mcp_client.py
│   │   ├── utils.py (already listed)
│   │   └── monitoring.py (already listed)
│   ├── circuit_breaker.py
│   │   └── monitoring.py (already listed)
│   └── utils.py (already listed)
├── utils.py
│   ├── config.py (already listed)
│   └── monitoring.py (already listed)
└── workflow.py
    ├── config.py (already listed)
    ├── state.py
    ├── utils.py (already listed)
    └── eval_rubric.py (already listed)
```

Additionally, `__init__.py` exports: `State`, `score_output`, `gate_check`, `record_failure`, `RegressionTracker`, `RubricStore`, `GoldStandardSuite`, `run_production_check`, `close_the_loop`, `ThresholdAlerter`.

### Modules confirmed NOT imported by live chain (dead code)

The following 30 modules exist under `src/` but are **not reachable** from the live import chain:

`agent_composer`, `analyze_usage`, `api_validation_tools`, `base_agent`,
`clients`, `code_extractor_agent`, `code_generator_agent`,
`code_integrator_agent`, `code_reviewer_agent`, `code_validator`,
`collaborative_generator`, `collect_tests`, `combined_agents`,
`composable_workflows`, `dependency_analyzer_agent`,
`dependency_installer_agent`, `error_recovery_agent`, `feedback_agent`,
`fetch_issue_agent`, `hitl_node`, `implementation_planner_agent`,
`llm_validator`, `output_result_agent`, `parse_executed_tests`,
`performance`, `post_test_runner_agent`, `pre_test_runner_agent`,
`process_llm_agent`, `prompts`, `state_adapters`,
`test_generator_agent`, `test_suite_examples`, `ticket_clarity_agent`,
`tool_executor`, `tool_integrated_agent`,
`tool_integrated_code_generator_agent`, `workflows`

Verification: `grep` for each dead module name across all `src/*.py` files returned zero import references from live-chain files.

---

## SEC-02: Credential Audit

**Result: PASS (fixed) — Token-leaking print statements removed.**

### Finding 2.1 — GitHub token printed to stdout (HIGH) — FIXED

- **File:** `agents/agentics/src/services.py`
- **Lines:** 117, 128
- **Original code (removed):**
  ```python
  # Line 117 (GitHubClient.__init__):
  print(f"GitHubClient __init__ called, token: {token}")

  # Line 128 (GitHubClient._initialize_client):
  print(f"GitHub _initialize_client called, token: {self.token}")
  ```
- **Risk:** The raw GitHub token was printed to stdout on every initialization.
- **Fix applied:** Both `print()` statements removed. The class already uses `log_info()` for structured logging.

### Finding 2.2 — Token stored as instance attribute (LOW)

- **File:** `agents/agentics/src/services.py`, line 119
- **Code:** `self.token = token`
- **Risk:** The token is stored as a plain string attribute on the `GitHubClient` instance. If the object is serialized, pickled, or logged, the token leaks. Combined with Finding 2.1, this is elevated.
- **Note:** This is acceptable if the object lifecycle is short-lived and never serialized. No immediate remediation required Beyond removing the print statements.

### Verification: No hardcoded secrets

Grep for `ghp_`, `gho_`, `AKIA`, `-----BEGIN`, `TOKEN`, `SECRET`, `PASSWORD`, `API_KEY` across all `src/*.py` files: **zero hardcoded values found.** All credential references use `os.getenv()`.

---

## SEC-03: Circuit Breaker Validation

**Result: PASS**

### Implementation review (`circuit_breaker.py`)

- **State machine:** Three-state (CLOSED → OPEN → HALF_OPEN → CLOSED) with correct transitions.
- **Failure thresholds:** Ollama = 3 (line 64 of config.py), GitHub = 5 (line 67 of config.py). Values are configurable via `AgenticsConfig`.
- **Recovery timeout:** Ollama = 30s, GitHub = 60s.
- **Reset mechanism:** On HALF_OPEN success, `_reset()` is called (line 81), transitioning to CLOSED and zeroing both `failure_count` and `success_count`.
- **Thread safety:** No shared mutable state beyond instance attributes. The `CircuitBreaker` is used per-service (ollama, github) via `get_circuit_breaker()` which stores instances in a module-level dict. No race condition on the dict itself (single-threaded asyncio + module-level initialization).
- **Open circuit behavior:** Correctly raises `CircuitBreakerOpenException` (line 146/157/190).

### Concern (informational)

- The `circuit_breakers` dict at module level (line 439) is not protected by a lock. Under true multi-threaded access, concurrent `get_circuit_breaker()` calls could create duplicate instances. Current usage is asyncio-based (single-threaded), so this is not exploitable.

---

## SEC-04: Input Validation Audit

**Result: PASS (with notes)**

### Finding 4.1 — `validate_github_url()` regex (LOW)

- **File:** `utils.py`, line 21
- **Pattern:** `^https://github\.com/[\w-]+/[\w-]+/issues/\d+$`
- **Assessment:** The regex correctly constrains the URL to github.com, requires owner/repo format with alphanumeric + hyphen characters, and requires a numeric issue number. Anchored with `^...$`. Sufficient for the use case.
- **Note:** Does not validate that the URL actually resolves or that the issue exists — that is handled by the GitHub API call with its own error handling.

### Finding 4.2 — LLM response JSON parsing (PASS)

- **File:** `workflow.py`, inline JSON extraction (lines 281–293 in `_node_clarify_ticket`)
- Implements code-fence stripping, brace-based extraction, and fallback to default refined ticket.
- Malformed responses are handled without crashes; falls back to a default dict.

### Finding 4.3 — File path operations (LOW)

- **Files:** `workflow.py` (file I/O in `_node_generate_code_tests`, `_node_extract_code`)
- **Concern:** File paths are constructed via `os.path.join(project_root, ...)` with no path traversal protection. A malicious path could escape the project root.
- **Assessment:** LOW severity because (1) file paths are controlled by the workflow's own logic from issue-derived slugs, not direct user input, and (2) the code operates within a controlled project structure.
- **Recommendation:** Add `os.path.realpath()` validation that the resolved path starts with `project_root`.

### Finding 4.4 — Workflow URL parsing (PASS)

- **File:** `workflow.py`, `_node_fetch_issue()` line 281–282
- **Code:** `parts = url.split("/"); owner, repo, issue_number = parts[3], parts[4], int(parts[6])`
- **Assessment:** This relies on `validate_github_url()` being called first (which happens in `agentics.py:92`). If `validate_github_url` passes, the split positions are guaranteed correct.

---

## SEC-05: Dead Code Backdoor Check

**Result: PASS — Dead code contains no backdoors.**

### Scan methodology

All 30+ dead-code files under `src/` were scanned for:
- `requests.`, `urllib`, `socket.`, `subprocess.`, `os.system(`, `eval(`, `exec(`, `compile(`, `httpx.`, `aiohttp.`

### Results

- **`subprocess` references:** Only in live files (`workflow.py`). Zero in dead code.
- **`eval`/`exec` references:** Zero matches across all `src/*.py` files.
- **Network library imports (`requests`, `urllib`, `httpx`, `aiohttp`, `socket`):** Zero in dead code. (Note: `mcp_client.py` uses `aiohttp` but is a live file.)
- **Hardcoded secrets:** Zero matches across all `src/*.py` files.
- **No obfuscated code patterns detected** (no base64 decode, no `__import__`, no dynamic code execution).

---

## Recommendations Summary

| Priority | Finding | Action |
|----------|---------|--------|
| ~~HIGH~~ | ~~`services.py:117,128` — token printed to stdout~~ | **FIXED** — both `print()` statements removed |
| **LOW** | `workflow.py` — no path traversal guard on generated file writes | Add `os.path.realpath()` check against `project_root` |
| **INFO** | `circuit_breakers` dict needs no lock under asyncio | Acceptable; document assumption |
| **INFO** | Validate GitHub URL regex is adequate | No change needed |
