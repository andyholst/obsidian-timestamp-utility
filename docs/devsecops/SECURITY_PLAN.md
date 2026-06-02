# Security Analyst — Action Plan

## Objective
Audit the codebase for security vulnerabilities, validate the import chain, ensure dead code doesn't contain backdoors or credential leaks, and verify circuit breaker integrity.

## Tasks

### SEC-01: Import Chain Verification
Verify that the live code import chain is clean and no dead code is reachable:
```bash
# Find all imports in the live codebase
grep -rn "from \." agents/agentics/src/ --include="*.py" | grep -v "__pycache__"
# Verify no dead file is imported
grep -rn "code_validator\|collaborative_generator\|composable_workflows\|llm_validator\|ticket_clarity_agent\|code_integrator_agent\|code_extractor_agent\|test_generator_agent\|error_recovery_agent\|pre_test_runner_agent\|process_llm_agent\|post_test_runner_agent\|combined_agents\|prompts\|state_adapters\|performance\|base_agent\|dependency_analyzer\|feedback_agent\|implementation_planner\|agent_composer\|tool_integrated\|clients\|fetch_issue_agent\|collect_tests\|analyze_usage\|parse_executed\|hitl_node\|tool_executor\|output_result\|api_validation\|workflows" agents/agentics/src/ --include="*.py"
```

**Expected**: Zero matches. If any found, add to deletion list.

### SEC-02: Credential Audit
Check that dead code doesn't contain hardcoded credentials or API keys:
```bash
grep -rn "token\|secret\|password\|api_key\|private" agents/agentics/src/ --include="*.py" | grep -v "#" | grep -v "test_" | grep -v "__pycache__"
```

**Expected**: Only references to env vars (e.g., `os.getenv("GITHUB_TOKEN")`), no hardcoded values.

### SEC-03: Circuit Breaker Validation
Verify the circuit breaker properly protects against cascading failures:
1. Review `circuit_breaker.py` for race conditions
2. Verify failure thresholds are appropriate (3 for Ollama, 5 for GitHub)
3. Check that circuit breaker state resets properly
4. Write test: verify open circuit blocks requests
5. Write test: verify half-open → closed transition after success

### SEC-04: Input Validation Audit
Check that all inputs from external sources (GitHub API, LLM responses, file paths) are validated:
1. URL validation in `validate_github_url()` — check regex is strict enough
2. LLM response parsing — verify JSON parsing handles malformed responses
3. File path operations — check for path traversal vulnerabilities

### SEC-05: Dead Code Backdoor Check
Before deletion, verify dead files don't contain:
- Network calls to external servers
- File system writes outside the project
- Credential harvesting
- Obfuscated code

**Approach**: Run `grep -rn "requests\|urllib\|socket\|subprocess\|os.system\|eval\|exec\|compile" agents/agentics/src/` and review each match.

## Deliverables
- SEC-01: Import chain verification report (pass/fail)
- SEC-02: Credential audit report (pass/fail)
- SEC-03: Circuit breaker test cases (2 new tests)
- SEC-04: Input validation gaps documented
- SEC-05: Dead code backdoor scan (pass/fail)

## Sign-off Criteria
- No dead code is reachable from live import chain
- No hardcoded credentials anywhere
- Circuit breaker tests pass
- Input validation covers all external inputs
- Dead code is clean for deletion
