## Why

After `make run-agentics` refactors/generates the Python agentic code (via the
`agentic-self-correct-loop` change), we must **prove the refactored code is still correct**
before trusting it. Today the agentic test suite is mock-dominated:

- Unit tests mock heavily (e.g. `test_services_unit.py` alone has ~470 mock references);
  they assert call shapes, not real behaviour of the code under test.
- Integration/e2e tests also `@patch`/`monkeypatch` Ollama/HTTP, so they never
  exercise the real LLM call path.

If `run-agentics` refactors the Python (e.g. the `openspec_loader` / `code_integrator`
wiring we added), a green suite can still hide broken real-logic. We need:

1. A **post-generation verification gate**: after `run-agentics`, automatically re-run
   `make test-agents-unit` AND `make test-agents-integration` (real, not mocked) to confirm
   the refactored agentic code is still valid and in sync.
2. A **refactor of the agentic tests** so unit tests test the *real* logic of the
   Python modules (deterministic units: parsing, state adapters, omission guard, export_name
   assembly, UUID/prompt construction) and integration/e2e tests make **real** Ollama
   calls (no mocks) — they must actually hit `OLLAMA_HOST` and validate generated TS.

## What Changes

- `agents/agentics/tests/unit/*`: refactor so unit tests test the **real** modules
  (deterministic logic: parsing, state adapters, `openspec_loader.load_change`,
  `code_integrator` assembly, `post_test_runner` metrics, export_name,
  omission-guard). Mocks are allowed ONLY for **external calls** (GitHub API,
  Ollama/LLM HTTP, network, FS boundaries) — never to replace the unit under test.
- `agents/agentics/tests/integration/*` + e2e: **remove** `@patch`/`monkeypatch` on
  Ollama/GitHub; make **real** calls to `OLLAMA_HOST` (running Ollama) and,
  where the test fetches an issue, the **real** GitHub API (`GITHUB_TOKEN`), and
  assert on the real generated TS.
- `Makefile`: add a `verify-agentics-after-run` (or extend `test-agents`) target that
  runs unit + integration after `run-agentics`, so the loop gate includes agentic-suite
  verification. `make run-agentics` may depend on / invoke it, or it is a separate
  explicit step in the loop phase.
- Wire this into the `agentic-self-correct-loop` loop: after the TS self-correct loop
  passes, the **agentic** suite must also pass (the Python code that produced it is
  still valid).

## Capabilities

### New Capabilities
- `agentic-tests-real-logic`: After `run-agentics`, the agentic unit + integration/e2e
  tests MUST be re-run. Unit tests MUST exercise the **real** Python logic (no mocks for
  deterministic units); integration/e2e tests MUST make **real** Ollama calls (no mocks),
  proving the refactored agentic code is valid and in sync with the generated TS.

### Modified Capabilities
- `agentic-self-correct-loop` (from `agentic-self-correct-loop` change): its success
  gate additionally requires the agentic suite (unit + real-integration) to pass after the
  run, so a refactor that breaks the Python is caught.

## Impact

- Python agentic tests: `agents/agentics/tests/unit/*`, `agents/agentics/tests/integration/*`.
- Makefile: new `verify-agentics-after-run` (or `test-agents` extension); `run-agentics`
  loop phase references it.
- CI / loop: post-`run-agentics` verification now covers both the generated TS AND the
  Python that generated it.
