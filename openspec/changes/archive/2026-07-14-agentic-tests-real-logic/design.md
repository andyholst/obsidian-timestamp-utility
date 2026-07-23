# Design — agentic-tests-real-logic

## Current state
- `agents/agentics/tests/unit/*` is mock-dominated: e.g. `test_services_unit.py` ~470
  mock references; tests assert call shapes, not real behaviour of the unit under test.
- `agents/agentics/tests/integration/*` + e2e also `@patch`/`monkeypatch` llama/GitHub,
  so they never exercise the real LLM call path.
- `Makefile` has `test-agents-unit`, `test-agents-unit-mock`, `test-agents-integration`,
  `validate-test_suite`, but NO gate that re-runs the agentic suite automatically
  AFTER `run-agentics` refactors the Python.

## Change plan
1. **Unit refactor (real logic, mock external only).** For each deterministic module,
   rewrite its unit test to call the REAL implementation and assert real outputs:
   - `openspec_loader.load_change` → real file reads of a fixture change dir; assert the
     synthesized `ticket_content` shape. Mock ONLY the GitHub HTTP call when present.
   - `state_adapters` / `state.py` → real state transforms; assert real transitions.
   - `code_integrator` assembly / `export_name` derivation → real string assembly;
     assert deterministic output.
   - `post_test_runner` parse/metrics helpers → real regex on a sample log; assert
     parsed counts.
   - `code_generator` / `test_generator` prompt construction → real prompt build;
     mock ONLY the llama HTTP boundary.
   Rule: a mock may wrap `requests.get/post`, `llama(...).chat`, `open()` on a
   network path, or `subprocess` — never the function/class being tested.
2. **Integration/e2e = real calls.** Remove `@patch`/`monkeypatch` on llama and GitHub.
   Point tests at the real `LLAMA_HOST` (the running llama) and, for issue-fetch
   tests, the real GitHub API (`GITHUB_TOKEN`). Assert on real generated TS. Keep the
   `pytest -m e2e` / integration markers; these require llama (and GitHub token) to run.
3. **Post-run gate in Makefile.** Add `verify-agentics-after-run` (or extend `test-agents`)
   that runs `make test-agents-unit` + `make test-agents-integration` after `run-agentics`.
   Wire it so the loop phase (AGENTS.md / `agentic-self-correct-loop`) includes
   "agentic suite green" as a completion criterion.
4. **Honesty.** The loop reports `agentic_tests_passed=False` + failing test name if the
   re-run fails (same honesty rule as the TS self-correct loop).

## Interaction
- Extends `agentic-self-correct-loop`: its success gate additionally requires the agentic
  suite (unit + real-integration) to pass after `run-agentics`, so a refactor that
  breaks the Python is caught.
- `docker-make-no-dagger` owns `run-agentics` + `test-agents-*` targets (docker-only).
