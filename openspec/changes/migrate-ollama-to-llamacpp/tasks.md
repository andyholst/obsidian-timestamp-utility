# Tasks for migrate-ollama-to-llamacpp

This change updates the loop and e2e wiring from the old Ollama backend to llama.cpp (port unchanged at 127.0.0.1:11434), pinning model qwen3.6-35b-a3b so live tests actually run instead of failing / skipping due to wrong model name or missing ollama process.

## Contract
ALL changes MUST keep the same port 127.0.0.1:11434 and same JSON request shapes; only backend identity and model name change.
No new external dependencies (no ollama binary required on host).

## Test Contract
Live unit/e2e tests MUST run successfully against llama.cpp (qwen3.6-35b-a3b) without Ollama installed:
- make loop-harness, loop-unit-real, loop-e2e gates should not fail due to missing/old Ollama model references.

## Tasks

1.0 [ ] Update Makefile model/host configuration
    1.1 [x] Change OLLAMA_MODEL and OLLAMA_CODE_MODEL (or new equivalents) to qwen3.6-35b-a3b instead of old sorc/qwen3.5-claude-4.6-opus references.
    1.2 [x] Verify OLLAMA_HOST remains http://localhost:11434 but rename variables (e.g., LLAMA_CPP_HOST) if needed to avoid confusion (optional — consistency preferred).

2.0 [x] Update container envs / agentics configs
    2.1 [x] Ensure agents.yaml container run commands pass correct model name for llama.cpp (qwen3.6-35b-a3b) so live tests hit the right model.
    2.2 [ ] Confirm any OLLAMA_TIMEOUT/OLLAMA_RETRY settings continue to apply under llama.cpp.

3.0 [ ] Ensure e2e/live tests call llama.cpp with correct JSON payload (compatible API shape at port 11434)
    3.1 [ ] Confirm inference helper(s) in agents/agentics/src use llama.cpp compatible JSON requests and the new model name instead of old Ollama-specific calls.

4.0 [ ] Verify loop gates actually run on llama.cpp
    4.1 [ ] Run make loop-unit-real and confirm live unit tests complete and use qwen3.6-35b-a3b.
    4.2 [ ] Run make loop-e2e and confirm e2e tests succeed against llama.cpp without Ollama present.

5.0 [ ] No-op check: ensure old ollama dependencies are removed or guarded (if any) so live tests never fail solely because ollama is not installed/running.
