# Dagger.io Module for Obsidian Timestamp Utility

## Usage

Use `make -f Makefile.dagger <target>` as drop-in replacement for original
Makefile. Maintains deps, phony targets, vars, checks (check-deps, check-github,
check-mcp-start, fix-perms, create-logs).

Examples:

```bash
make -f Makefile.dagger build-app
make -f Makefile.dagger test-agents-unit
make -f Makefile.dagger test-agents-integration
make -f Makefile.dagger test-agents-unit-verbose  # interactive (dagger do)
make -f Makefile.dagger release
```

## Direct Dagger Calls (CI / no-make)

```bash
dagger call build_app --ollama-model=qwen2.5:14b
dagger call test_agents_unit --ollama-model=qwen2.5:14b
dagger do test_agents_unit_verbose --ollama-model=qwen2.5:14b  # interactive
dagger call test_agents_integration --github-token=secret:github_token --ollama-model=qwen2.5:14b
```

Secrets: `dagger secrets add github_token ghp_xxx`

## Prerequisites

Host services:

- Ollama: http://localhost:11434
- MCP bridge: http://localhost:3003 (auto-start if missing via check-mcp-start)

## Initialization

```bash
dagger project init --sdk=python
dagger project update
```

## Migration Guide

1. **Gradual**: `make -f Makefile.dagger` alongside original Makefile.
2. **Full**: Delete original Makefile; use direct `dagger call` / `dagger do`.
3. Remove docker-compose-files/, docker-files/ once migrated.
4. Update docs to Dagger commands.
