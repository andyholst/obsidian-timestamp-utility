## ADDED Requirements
### Capability: llamacpp-server

The system MUST use llama.cpp server (not Ollama) as the live inference backend for all e2e and real-unit tests. Server is reachable at 127.0.0.1:11434 and serves model qwen3.6-35b-a3b.

### Requirement: pin-model-to-qwen3.6-35b-a3b
The Makefile + container configs MUST pin the reasoning/code model to qwen3.6-35b-a3b when invoking llama.cpp.

#### Scenario: e2e-tests-target-correct-model
- WHEN `make loop-e2e` or live unit tests run inside containers calling 127.0.0.1:11434
- THEN the requests use model qwen3.6-35b-a3b (not an old Ollama-specific name)

### Requirement: no-ollama-dependency-in-loop
Remove or guard all hardcoded Ollama-specific calls / references in loop-facing configs so tests do not fail when only llama.cpp is running.

#### Scenario: live-tests-never-call-ollama-binary
- WHEN a live test needs inference and `OLLAMA_HOST`/host-like envs point at 127.0.0.1:11434
- THEN calls are performed via llama.cpp-compatible HTTP API (JSON) to that endpoint

### Requirement: host-port-and-compat-unchanged
llama.cpp MUST serve on 127.0.0.1:11434 with a JSON API shape compatible with existing Ollama-style requests so agentics code only needs a model-name update, not a protocol rewrite.

#### Scenario: existing-inference-clients-work-without-changes
- WHEN agentics inference clients hit 127.0.0.1:11434 with the same JSON payload shapes used previously
- THEN llama.cpp responds and completes the request without requiring format changes

## Test Contract

### Requirement: loop-e2e-run-real-on-llamacpp
Live e2e gates MUST run against llama.cpp:

- WHEN `make loop-e2e` executes on a host with llama.cpp running at 127.0.0.1:11434 (no Ollama installed)
- THEN the e2e tests complete using qwen3.6-35b-a3b and do NOT error / hang due to missing Ollama

### Requirement: loop-unit-real-run-on-llamacpp
Live unit tests MUST run against llama.cpp:

- WHEN `make loop-unit-real` executes on a host with llama.cpp at 127.0.0.1:11434
- THEN tests use qwen3.6-35b-a3b successfully instead of an Ollama-only model path
