SHELL := /bin/bash
.ONESHELL:
.DELETE_ON_ERROR:
.SUFFIXES:

# Load .env file if it exists (for local secrets like GITHUB_TOKEN)
ifneq (,$(wildcard .env))
include .env
export
endif

REPO_NAME := obsidian-timestamp-utility
TAG       := $(shell node -p "require('./package.json').version")

DAGGER_ENGINE_HOST := localhost
DAGGER_ENGINE_PORT := 1234
export DAGGER_ENGINE_HOST DAGGER_ENGINE_PORT
DAGGER    := $(shell pwd)/bin/dagger
PATH      := ./bin:$(PATH)
export PATH

HOST_UID  := $(shell id -u)
HOST_GID  := $(shell id -g)
export HOST_UID HOST_GID

OLLAMA_MODEL      ?= sorc/qwen3.5-claude-4.6-opus:9b
OLLAMA_CODE_MODEL ?= sorc/qwen3.5-claude-4.6-opus:9b
OLLAMA_NUM_CTX    ?= 8192
OLLAMA_NUM_PREDICT ?= 2048
# Ollama host for Dagger containers: use the socat proxy on port 11435
# which forwards to Ollama on 127.0.0.1:11434. The proxy listens on 0.0.0.0.
# The proxy is started automatically by start-socat below.
# Detect host IP dynamically for container access.
HOST_IP           := $(shell hostname -I 2>/dev/null | awk '{print $$1}')
OLLAMA_HOST       := http://$(HOST_IP):11435
SOCAT_PORT        := 11435
OLLAMA_LOCAL_PORT := 11434
ISSUE_URL         ?= https://github.com/andyholst/obsidian-timestamp-utility/issues/20
TEST_FILTER       ?=
INTEGRATION_TEST_FILTER ?=
OLLAMA_TIMEOUT    ?= 300
DAGGER_TIMEOUT    ?= 600
TYPE              ?=
export TEST_FILTER INTEGRATION_TEST_FILTER OLLAMA_TIMEOUT DAGGER_TIMEOUT TYPE OLLAMA_HOST

DOCKER_SOCK := $(shell \
	if [ -S /var/run/docker.sock ]; then echo /var/run/docker.sock; \
	elif [ -S /run/containerd/containerd.sock ]; then echo /run/containerd/containerd.sock; \
	elif [ -S $(XDG_RUNTIME_DIR)/containerd/containerd.sock ]; then echo $(XDG_RUNTIME_DIR)/containerd/containerd.sock; \
	elif [ -S $(XDG_RUNTIME_DIR)/containerd-rootless/api.sock ]; then echo $(XDG_RUNTIME_DIR)/containerd-rootless/api.sock; \
	else echo ""; fi)
DOCKER_SOCK_ARG := $(if $(DOCKER_SOCK),--docker-sock=unix://$(DOCKER_SOCK),)

.PHONY: help all \
        install-dagger sync-pipeline-deps ensure-dagger-ready generate-sdk setup-dev \
        check-engine start-engine stop-engine \
        build-app test-app changelog release \
        lint-python \
        build-image-agents test-validator format \
        test-agents-unit test-agents-unit-mock test-agents-integration test-agents-integration-fast test-agents-e2e \
        test-agents-unit-verbose test-agents-integration-verbose \
        test-agents-unit-fail-verbose test-agents-integration-fail-verbose \
        test-agents-unit-watch test-agents-integration-watch \
        validate-test_suite test-agents test \
        run-agentics \
        check-deps check-github check-issue-url check-ollama check-mcp check-secrets \
        fix-perms create-logs \
        start-mcp stop-mcp \
        start-socat stop-socat \
        generate-requirements \
        collect-tests collect-executed \
        stop-containers \
        clean clean-cache clean-logs dagger-clean clean-oci \
        clean-dagger-cache clean-dagger-engine nuke-dagger

.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "obsidian-timestamp-utility Makefile (validated)"
	@echo "Core dev: setup-dev test validate-makefile clean"
	@echo "=================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-35s\033[0m %s\n", $$1, $$2}'

all: build-app test-app release ## Full pipeline

install-dagger: ## Install Dagger CLI
	@./scripts/install_dagger.sh

sync-pipeline-deps: ## Sync Dagger module dependencies
	@cd dagger-pipeline && npm ci || true

generate-sdk: ## Generate Python SDK
	@echo "Generating Dagger Python SDK..."
	@cd dagger-pipeline && $(DAGGER) develop || echo "SDK generation failed (non-fatal)"

ensure-dagger-ready: install-dagger sync-pipeline-deps start-engine check-engine ## Ensure Dagger is ready for real runs

setup-dev: ensure-dagger-ready create-logs fix-perms ## One-command dev setup with validation

check-engine: ## Check if Dagger engine is running
	@./scripts/engine-wrapper.sh check

start-engine: ## Minimal: Install Dagger CLI + start engine
	./scripts/install_dagger.sh
	./scripts/engine-wrapper.sh start

stop-engine: ## Stop Dagger engine
	@./scripts/engine-wrapper.sh stop

build-app: ensure-dagger-ready ## Build Obsidian plugin
	@$(DAGGER) call -m dagger-pipeline build-app --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID) export --path ./

test-app: build-app ## Test the built plugin
	@$(DAGGER) call -m dagger-pipeline test-app --source=.
	@echo "=== Plugin test output above ==="
	@$(DAGGER) call -m dagger-pipeline fix-perms --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID)

validate-ts: ## Fast TypeScript validation (no Dagger, runs tsc directly)
	@echo "Running TypeScript validation..."
	@ERRS=$$(npx tsc --noEmit --ignoreDeprecations 6.0 --pretty false 2>&1 | grep -c "error TS" || true); \
	if [ "$$ERRS" -gt 0 ]; then \
		echo "TypeScript errors found: $$ERRS"; \
		npx tsc --noEmit --ignoreDeprecations 6.0 --pretty false 2>&1 | grep "error TS" | head -20; \
		exit 1; \
	fi
	@echo "TypeScript validation complete"

format-ts: ## Format TypeScript files with prettier
	@echo "Formatting TypeScript files..."
	@npx prettier --write src/main.ts src/__tests__/main.test.ts 2>&1 || true
	@echo "Formatting complete"

validate-tests: ## Fast test validation (runs jest directly, no Dagger)
	@echo "Running test validation..."
	@npx jest --no-cache --passWithNoTests 2>&1
	@echo "Test validation complete"

changelog: ensure-dagger-ready ## Generate CHANGELOG.md
	@$(DAGGER) call -m dagger-pipeline changelog --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID) export --path CHANGELOG.md

release: clean build-app ## Create release + ZIP check
	@if [ -z "$(TAG)" ]; then echo "Error: TAG could not be determined from package.json" >&2; exit 1; fi
	@$(DAGGER) call -m dagger-pipeline release --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID) export --path release || (echo "Error: Release pipeline failed. Check Dagger logs and npm build." >&2; exit 1)
	@$(DAGGER) call -m dagger-pipeline release-zip-check --source=. --repo-name=$(REPO_NAME) --tag=$(TAG) || (echo "Error: Release ZIP validation failed for $(REPO_NAME)-$(TAG).zip. Verify artifacts in release/." >&2; exit 1)

lint-python: ensure-dagger-ready ## Run ruff + mypy linting on Python code
	@$(DAGGER) call -m dagger-pipeline lint-python --source=.

build-image-agents: ensure-dagger-ready ## Build agent Docker image (slow: downloads ~1.5GB CUDA/PyTorch)
	@$(DAGGER) call -m dagger-pipeline build-image-agents --source=.

test-validator: ## Dedicated validator test (runs dev mode)
	@cd scripts/validate-makefile && \
		if [ ! -d ".venv" ] || [ ! -f ".venv/bin/activate" ]; then \
			python3 -m venv .venv; \
		fi && \
		. .venv/bin/activate && \
		python -m pip install --upgrade pip -q && \
		pip install -q -r requirements.txt --no-cache-dir && \
		python validate_makefile.py --mode clean
	@echo "Validator test completed."

format: ensure-dagger-ready ## Format code with ruff (via Dagger pipeline)
	@$(DAGGER) call -m dagger-pipeline format --source=.

test-agents-unit: ensure-dagger-ready fix-perms ## Unit tests for agents (export results/)
	@$(DAGGER) call -m dagger-pipeline test-agents-unit \
		--source=. \
		--ollama-model=$(OLLAMA_MODEL) \
		--ollama-host=$(OLLAMA_HOST) \
		--test-filter=$(TEST_FILTER) \
		--host-uid=$(HOST_UID) \
		--host-gid=$(HOST_GID) \
		export --path results
	@echo "=== Unit test results ==="
	@cat results/executed_tests_unit.txt 2>/dev/null | tail -20 || echo "(no results file)"

test-agents-unit-mock: ensure-dagger-ready fix-perms ## Mocked unit tests (fast, no Ollama)
	@$(DAGGER) call -m dagger-pipeline test-agents-unit-mock \
		--source=. \
		--test-filter=$(TEST_FILTER) \
		--host-uid=$(HOST_UID) \
		--host-gid=$(HOST_GID)
	@echo "=== Mock unit test output above ==="

test-agents-integration: ensure-dagger-ready fix-perms check-github start-socat ## Full integration tests (needs Docker socket + tokens)
	@$(DAGGER) call -m dagger-pipeline test-agents-integration \
		--source=. $(DOCKER_SOCK_ARG) \
		--github-token=$(GITHUB_TOKEN) \
		--ollama-model=$(OLLAMA_MODEL) \
		--ollama-host=$(OLLAMA_HOST) \
		--test-filter="$(INTEGRATION_TEST_FILTER)" \
		--ollama-timeout=$(OLLAMA_TIMEOUT) \
		--host-uid=$(HOST_UID) \
		--host-gid=$(HOST_GID) \
		export --path results
	@echo "=== Integration test results ==="
	@cat results/executed_tests_integration.txt 2>/dev/null | tail -30 || echo "(no results file)"

test-agents-integration-fast: INTEGRATION_TEST_FILTER = --maxfail=1 -k not slow ## Fast integration tests (fail fast, skip slow)
test-agents-integration-fast: test-agents-integration

test-agents-e2e: INTEGRATION_TEST_FILTER = -m e2e ## End-to-end tests only
test-agents-e2e: test-agents-integration

test-agents-unit-verbose: ensure-dagger-ready check-deps create-logs ## Verbose unit tests + logs
	@$(DAGGER) call -m dagger-pipeline test-agents-unit-verbose \
		--source=. \
		--ollama-model=$(OLLAMA_MODEL) \
		--ollama-host=$(OLLAMA_HOST) \
		--test-filter=$(TEST_FILTER) \
		--host-uid=$(HOST_UID) \
		--host-gid=$(HOST_GID) \
		export --path results
	@echo "=== Verbose unit test results ==="
	@cat results/verbose_unit.log 2>/dev/null | tail -30 || echo "(no results file)"
	@$(DAGGER) call -m dagger-pipeline fix-perms --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID)

test-agents-integration-verbose: ensure-dagger-ready check-deps check-github create-logs start-socat ## Verbose integration tests + logs
	@$(DAGGER) call -m dagger-pipeline test-agents-integration-verbose \
		--source=. $(DOCKER_SOCK_ARG) \
		--github-token=$(GITHUB_TOKEN) \
		--ollama-model=$(OLLAMA_MODEL) \
		--test-filter=$(TEST_FILTER) \
		--ollama-timeout=$(OLLAMA_TIMEOUT) \
		--host-uid=$(HOST_UID) \
		--host-gid=$(HOST_GID) \
		export --path results
	@echo "=== Verbose integration test results ==="
	@cat results/verbose_integration.log 2>/dev/null | tail -30 || echo "(no results file)"
	@$(DAGGER) call -m dagger-pipeline fix-perms --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID)

test-agents-unit-fail-verbose: TEST_FILTER = "--last-failed" ## Re-run only previously failed unit tests (verbose)
test-agents-unit-fail-verbose: test-agents-unit-verbose

test-agents-integration-fail-verbose: TEST_FILTER = "--last-failed" ## Re-run only previously failed integration tests (verbose)
test-agents-integration-fail-verbose: test-agents-integration-verbose

test-agents-unit-watch: ensure-dagger-ready check-deps create-logs ## Watch mode for unit tests
	@$(DAGGER) call -m dagger-pipeline test-agents-unit-watch \
		--ollama-model=$(OLLAMA_MODEL) \
		--test-filter=$(TEST_FILTER)
	@$(DAGGER) call -m dagger-pipeline fix-perms --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID)

test-agents-integration-watch: ensure-dagger-ready check-deps check-github create-logs ## Watch mode for integration tests
	@$(DAGGER) call -m dagger-pipeline test-agents-integration-watch \
		--github-token=$(GITHUB_TOKEN) \
		--ollama-model=$(OLLAMA_MODEL) \
		--test-filter=$(TEST_FILTER) \
		--ollama-timeout=$(OLLAMA_TIMEOUT)
	@$(DAGGER) call -m dagger-pipeline fix-perms --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID)

validate-test_suite: ensure-dagger-ready check-deps check-github ## Validate entire test suite (coverage, etc.)
	@$(DAGGER) call -m dagger-pipeline validate-test-suite \
		--source=. $(DOCKER_SOCK_ARG) \
		--github-token=$(GITHUB_TOKEN) \
		--ollama-model=$(OLLAMA_MODEL)
	@$(DAGGER) call -m dagger-pipeline fix-perms --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID)

test-agents: lint-python test-agents-unit-mock test-agents-integration validate-test_suite ## All agent tests
test: test-app test-agents ## All tests (app + agents)

run-agentics: check-deps check-github ## Run AI agentics workflow on GitHub issue (issue #20 by default)
	@echo "Running agentics with reasoning model: $(OLLAMA_MODEL), code model: $(OLLAMA_CODE_MODEL)"
	@echo "Issue URL: $(ISSUE_URL)"
	cd agents/agentics && \
		GITHUB_TOKEN=$(GITHUB_TOKEN) \
		OLLAMA_HOST=http://localhost:11434 \
		OLLAMA_MODEL=$(OLLAMA_MODEL) \
		OLLAMA_REASONING_MODEL=$(OLLAMA_MODEL) \
		OLLAMA_CODE_MODEL=$(OLLAMA_CODE_MODEL) \
		OLLAMA_NUM_CTX=$(OLLAMA_NUM_CTX) \
		OLLAMA_NUM_PREDICT=$(OLLAMA_NUM_PREDICT) \
		MCP_SERVER_URL=http://localhost:3003 \
		URL=$(ISSUE_URL) \
		PROJECT_ROOT=$(shell pwd) \
		TEST_ULTRA_FAST_MODE=1 \
		.venv/bin/python3.12 -m src.agentics 2>&1
	@echo "=== Agentics run complete ==="
	@ls -la src/main.ts src/__tests__/main.test.ts 2>/dev/null || echo "Note: generated files may be in a different location"

check-deps: check-ollama check-engine check-issue-url check-npm-deps ## Verify all external dependencies
check-npm-deps: ## Ensure npm devDependencies are installed
	@if [ ! -d node_modules/ts-jest ] || [ ! -d node_modules/jest ]; then \
		echo "Installing npm devDependencies..."; \
		npm install --legacy-peer-deps --include=dev 2>&1 | tail -5; \
	fi
check-github: ## Validate GitHub token
	@if [ -z "$(GITHUB_TOKEN)" ]; then echo "Error: GITHUB_TOKEN is required" >&2; exit 1; fi

check-issue-url: ## Validate ISSUE_URL for agentics
	@if [ -z "$(ISSUE_URL)" ] || ! echo "$(ISSUE_URL)" | grep -q '^https'; then echo "Error: Valid ISSUE_URL (https://...) is required" >&2; exit 1; fi

check-ollama: ## Check Ollama availability
	@curl -sf "http://localhost:11434/api/tags" > /dev/null 2>&1 && echo "Ollama OK" || echo "WARNING: Ollama not reachable at localhost:11434 (non-fatal)"

check-secrets: ensure-dagger-ready ## Scan for leaked secrets
	@$(DAGGER) call -m dagger-pipeline check-secrets --source=.

fix-perms: ensure-dagger-ready ## Fix file permissions (called automatically after most targets)
	@$(DAGGER) call -m dagger-pipeline fix-perms \
		--source=. \
		--host-uid=$(HOST_UID) \
		--host-gid=$(HOST_GID) || echo "Warning: fix-perms encountered issues (non-fatal)"

create-logs: ensure-dagger-ready ## Create log directory structure
	@$(DAGGER) call -m dagger-pipeline create-logs \
		--source=. \
		--host-uid=$(HOST_UID) \
		--host-gid=$(HOST_GID) \
		export --path ./logs

start-mcp: ensure-dagger-ready ## Start MCP as pure Dagger service (localhost:3003, Ctrl+C to stop)
	@$(DAGGER) call -m dagger-pipeline start-mcp --source=.

stop-mcp: ensure-dagger-ready ## Stop MCP Dagger service (prints instructions)
	@$(DAGGER) call -m dagger-pipeline stop-mcp --source=.
start-mcp-persist: ensure-dagger-ready create-logs ## Start MCP persistently in background (localhost:3003, logs: logs/mcp-persist.log)
	@if curl -s -f http://localhost:3003/health >/dev/null 2>&1; then echo "MCP already running on 3003"; exit 0; fi
	@nohup $(DAGGER) call -m dagger-pipeline start-mcp --source=. > logs/mcp-persist.log 2>&1 & echo $$! > .mcp.pid
	@sleep 8
	@cat .mcp.pid
	@curl -f http://localhost:3003/health >/dev/null 2>&1 && echo "MCP healthy" || echo "MCP starting (check logs/mcp-persist.log)"
stop-mcp-persist: ## Stop persistent MCP using PID file
	@if [ -f .mcp.pid ]; then kill $$(cat .mcp.pid) 2>/dev/null || true; rm -f .mcp.pid; echo "MCP persistent stopped"; else echo "No .mcp.pid found"; fi
	@curl -s http://localhost:3003/health >/dev/null 2>&1 && echo "Warning: port 3003 still active" || echo "MCP port free"

start-socat: ## Start socat proxy for Ollama (port 11435 -> 127.0.0.1:11434)
	@if ss -tlnp | grep -q ":$(SOCAT_PORT) "; then echo "Socat proxy already running on port $(SOCAT_PORT)"; exit 0; fi
	@echo "Starting socat proxy: 0.0.0.0:$(SOCAT_PORT) -> 127.0.0.1:$(OLLAMA_LOCAL_PORT)"
	@nohup socat TCP-LISTEN:$(SOCAT_PORT),fork,reuseaddr TCP:127.0.0.1:$(OLLAMA_LOCAL_PORT) > /dev/null 2>&1 & echo $$! > .socat.pid
	@sleep 1
	@ss -tlnp | grep -q ":$(SOCAT_PORT) " && echo "Socat proxy started" || echo "WARNING: socat proxy may not have started"

stop-socat: ## Stop socat proxy
	@if [ -f .socat.pid ]; then kill $$(cat .socat.pid) 2>/dev/null || true; rm -f .socat.pid; echo "Socat proxy stopped"; else echo "No .socat.pid found"; fi
	@ss -tlnp | grep -q ":$(SOCAT_PORT) " && echo "Warning: port $(SOCAT_PORT) still active" || echo "Socat port free"

generate-requirements: ensure-dagger-ready ## Regenerate pip-requirements files (slow: pip-compile resolves PyTorch/CUDA deps)
	@$(DAGGER) call -m dagger-pipeline generate-requirements \
		--source="./docker-files/pip-requirements" \
		export --path ./docker-files/pip-requirements

collect-tests: ensure-dagger-ready ## Collect test files (used by CI)
	@$(DAGGER) call -m dagger-pipeline collect-tests --source=. --type=$(TYPE)
	@$(DAGGER) call -m dagger-pipeline fix-perms --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID)

collect-executed: ensure-dagger-ready ## Collect executed tests (used by CI)
	@$(DAGGER) call -m dagger-pipeline collect-executed --source=. --type=$(TYPE)
	@$(DAGGER) call -m dagger-pipeline fix-perms --source=. --host-uid=$(HOST_UID) --host-gid=$(HOST_GID)

stop-containers: ## Stop all Dagger-managed containers
	@if [ -z "$(DOCKER_SOCK)" ]; then echo "ERROR: No Docker/containerd socket found." >&2; exit 1; fi
	@if command -v nerdctl >/dev/null 2>&1; then \
		nerdctl ps -q --filter label=dagger.io 2>/dev/null | xargs -r nerdctl stop 2>/dev/null || true; \
		echo "Stopped Dagger containers (nerdctl)."; \
	elif command -v docker >/dev/null 2>&1; then \
		docker ps -q --filter label=dagger.io 2>/dev/null | xargs -r docker stop 2>/dev/null || true; \
		echo "Stopped Dagger containers (docker)."; \
	else \
		echo "No container runtime found (nerdctl/docker) — skipping."; \
	fi

clean: clean-cache clean-logs stop-containers clean-dagger-engine ## Full clean (includes engine cleanup)
	@echo "Cleaning up build artifacts..."
	rm -rf dist release results coverage dagger-pipeline/sdk node_modules || true

clean-cache: ## Remove Python caches only
	find . -name "__pycache__" -type d -exec rm -rf {} + || true
	rm -rf .pytest_cache
	find . -name ".pytest_cache" -type d -exec rm -rf {} + || true

clean-logs: ## Remove all logs
	find . -name "logs" -type d -exec rm -rf {} + 2>/dev/null || true
	find . \( -name "*.logs" -o -name "*.log" \) -delete 2>/dev/null || true

dagger-clean: stop-engine ## Remove Dagger binaries and SDK cache
	@rm -rf bin/ tempbin/ dagger-pipeline/.dagger/sdk || true

clean-oci: ## Fast OCI nuke (nerdctl prune best practice)
	nerdctl system prune -a -f --volumes || true
	@echo "OCI pruned."

validate-makefile: ## Validate targets. MODE=dev/full/agents/build/clean or positional: make validate-makefile dev (core only, fast+recommended), full (all), agents/build/clean
	@cd scripts/validate-makefile && \
		if [ ! -d ".venv" ] || [ ! -f ".venv/bin/activate" ]; then \
			python3 -m venv .venv; \
		fi && \
		. .venv/bin/activate && \
		python -m pip install --upgrade pip -q && \
		pip install -q -r requirements.txt --no-cache-dir && \
		python validate_makefile.py --mode $(if $(MODE),$(MODE),$(word 2,$(MAKECMDGOALS)))

kill-dagger-shims: ## Kill stuck containerd-shim processes for Dagger
	@ps aux | grep 'containerd-shim.*dagger' | grep -v grep | awk '{print $$2}' | xargs -r kill 2>/dev/null || true
	@echo "Killed Dagger shims."

rm-stale-dagger-dirs: ## Remove stale Dagger container metadata dirs
	@rm -rf ~/.local/share/nerdctl/*/containers/default/*dagger* ~/.local/share/nerdctl/*/volumes/default/*dagger* || true
	@rm -rf ~/.local/share/containers/storage/*dagger* /var/lib/docker/*dagger* ~/.docker/*dagger* || true
	@echo "Removed stale Dagger dirs."

clean-dagger-cache: ## Fast local Dagger clean (no CLI call)
	rm -rf dagger-pipeline/sdk bin/dagger tempbin || true

clean-dagger-engine: stop-engine kill-dagger-shims rm-stale-dagger-dirs clean-dagger-cache dagger-clean stop-containers ## Full Dagger engine reset
	@echo "Dagger engine fully cleaned and reset."

nuke-dagger: kill-dagger-shims rm-stale-dagger-dirs clean-dagger-cache clean-oci stop-engine ## Fast nuclear (host cmds only)
	@echo "Dagger + OCI nuked (~5s, no CLI start)."
