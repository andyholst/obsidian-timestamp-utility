# Proposal: Replace langchain-ollama with langchain-openai

## Why

The host runs **llama.cpp's server** (`llama-server`) which serves an **OpenAI-compatible API** at `http://localhost:11434/v1/chat/completions`. The current code uses `langchain-ollama` and `ollama` Python packages, which speak Ollama's native protocol — this is incompatible with llama.cpp's server. The code has worked by accident (both servers share a compatible subset), but this is fragile and misleading.

## What Changes

- Replace `langchain-ollama` with `langchain-openai` in all dependency manifests
- Replace `ollama` Python package with `openai` package
- Rename all `ollama_*` config/env fields to `llama_*` (backwards-compatible aliases kept)
- Rename `OllamaClient` → `LlamaClient`, `OllamaLLM` → `OpenAI` (via langchain)
- Rename `OllamaError` → `LlamaError`
- Update all Makefile env vars (`OLLAMA_HOST` → `LLAMA_HOST`, `OLLAMA_MODEL` → `LLAMA_MODEL`, etc.) with backwards-compatible aliases
- Update docker-compose env vars and comments
- Update all test files, fixtures, and integration test fixer scripts
- Update AGENTS.md references

## Capabilities

- `llama-backend`: Agentic pipeline works with llama.cpp server (OpenAI-compatible API)

## Impact

- All dependency files: 4 files
- Core source: `config.py`, `services.py`, `exceptions.py`
- Agentics source: all files importing `langchain_ollama` or `OllamaClient`/`OllamaLLM`
- Tests: 8+ test files + 3 fixture files
- Makefile: env vars, targets, comments
- Docker compose: 1 file with env vars
- Script: `run-loop-harness.sh` comments
- AGENTS.md: ~10 references
