# Proposal: migrate the AI backend from Ollama to llama.cpp server with qwen3.6-35b-a3b

## Why

The loop containers currently expect an Ollama process at 127.0.0.1:11434 serving models like sorc/qwen3.5-claude-4.6-opus:9b.

The actual server is now llama.cpp (running on the same port with a compatible JSON API), serving model qwen3.6-35b-a3b. If we do not update the client-side wiring, live e2e/Live-unit tests will fail to reach a valid model and silently degrade or timeout.

This change standardizes ON llama.cpp as the inference backend and pins qwen3.6-35b-a3b as the model used across loops/e2e so real verification is honest and stable.

## What Changes

- Update Makefile model/host configuration to reflect llama.cpp (qwen3.6-35b-a3b) instead of Ollama-specific references.
- Ensure the agentics live-unit and e2e tests talk to llama.cpp-compatible endpoints at 127.0.0.1:11434.
- Update container envs and agent configs so LLM calls use llama.cpp with the correct model name.

## Capabilities

- Capability: llamacpp-server — all live AI tests use llama.cpp on 127.0.0.1:11434 serving qwen3.6-35b-a3b.

## Impact

- Breaking: any code hardcoded to Ollama API shapes or model names will no longer work unchanged; they must align with llama.cpp compatibility layer + this model name.
- Non-breaking: port remains 127.0.0.1:11434; the loop-harness structure is preserved, only backend identity + model pin change.
