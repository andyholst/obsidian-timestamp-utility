SHELL := /bin/bash
# Variables
CONTAINER_RUNTIME := $(shell command -v nerdctl || command -v docker)
ifeq ($(CONTAINER_RUNTIME),)
$(error "Neither nerdctl nor docker is installed")
endif
CONTAINERD_CMD := ./scripts/containerd_wrapper.sh
DOCKER_COMPOSE_FILE := docker-compose-files/tools.yaml
REPO_NAME := obsidian-timestamp-utility
VERSION := $(shell node -p "require('./package.json').version")
TAG := $(VERSION)
IMAGE_NAME := $(REPO_NAME):$(TAG)
DOCKER_COMPOSE_FILE_PYTHON := docker-compose-files/agents.yaml
HOST_UID := $(shell id -u)
HOST_GID := $(shell id -g)
export HOST_UID HOST_GID

.PHONY: all build-image build-app test-app release changelog clean clean-oci clean-cache clean-logs create-logs stop-containers test-agents-unit test-agents-unit-mock test-agents-integration test-agents-integration-fast check-deps test-agents build-image-agents run-agentics generate-requirements start-mcp stop-mcp check-mcp check-mcp-start test-agents-unit-verbose test-agents-integration-verbose test-agents-unit-fail-verbose test-agents-integration-fail-verbose test-agents-unit-watch test-agents-integration-watch validate-test-suite check-secrets lint-python

all: build-app test-app release

build-image:
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE) build --build-arg REPO_NAME=$(REPO_NAME)

build-app: build-image
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE) run --rm -e TAG=$(TAG) -e REPO_NAME=$(REPO_NAME) app /bin/bash -c "\
						npm install --loglevel=silly && \
						npm run build-package"

test-app: build-app
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE) run --rm -e TAG=$(TAG) -e REPO_NAME=$(REPO_NAME) app /bin/bash -c "\
						npm install --loglevel=silly && \
						npm test"

changelog: build-image
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE) run --rm -e TAG=$(TAG) -e REPO_NAME=$(REPO_NAME) app /bin/bash -c "\
						chmod +x /app/scripts/changelog.sh && \
						/app/scripts/changelog.sh"

release: clean build-app
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE) run --rm -e TAG=$(TAG) -e REPO_NAME=$(REPO_NAME) app /bin/bash -c "\
						chmod +x /app/scripts/release.sh && \
						find /app -name '*.sh' -exec dos2unix {} \; || { echo 'Error: dos2unix failed on some .sh files'; exit 1; } && \
						/app/scripts/release.sh"
		test -f release/release-timestamp-utility-$(TAG).zip || { echo "Release zip not created"; exit 1; }

clean: clean-cache clean-logs stop-containers
		@echo "🧹 Cleaning up build artifacts..."
		rm -rf release dist

clean-oci: clean clean-logs
		@echo "🧹 Stopping and removing all containers..."
		-$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) down --remove-orphans
		@echo "🗑️  Removing all images, volumes, and cache..."
		-$(CONTAINERD_CMD) system prune -a --volumes -f
		-$(CONTAINERD_CMD) image prune -a -f
		@echo "✨ OCI/Containerd cleanup completed!"

clean-cache:
		find . -name "__pycache__" -type d -exec rm -rf {} +
		find . -name ".pytest_cache" -type d -exec rm -rf {} +


clean-logs:
		find . -name "logs" -type d -exec rm -rf {} +
		find . -name "logs" -type f -delete
		find . -name "logs" -type l -delete
		find . -name "*.logs" -type f -delete
		find . -name "*.log" -type f -delete

create-logs:
		mkdir -p logs/failed logs/success && chmod -R 777 logs && ln -sf $(PWD)/logs agents/agentics/logs

stop-containers:
		./scripts/containerd_wrapper.sh -f docker-compose-files/agents.yaml down --remove-orphans
		./scripts/containerd_wrapper.sh -f docker-compose-files/tools.yaml down --remove-orphans

build-generate-requirements:
		$(CONTAINERD_CMD) build -t pip-requirements -f docker-files/pip-requirements/Dockerfile .

generate-requirements: build-generate-requirements
		$(CONTAINERD_CMD) run --rm -v $(PWD)/agents/agentics:/app pip-requirements

build-image-agents:
	@if ! $(CONTAINER_RUNTIME) image inspect agentics >/dev/null 2>&1; then \
		env HOST_UID=$(HOST_UID) HOST_GID=$(HOST_GID) $(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) build; \
	fi

run-agentics: build-image-agents check-deps
	$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm --remove-orphans agentics

test-agents-unit: build-image-agents check-deps
	$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm --remove-orphans -e TEST_FILTER="$(TEST_FILTER)" unit-test-agents


# Run unit tests using mocks only, without external dependencies (no GITHUB_TOKEN, Ollama, or MCP required)
test-agents-unit-mock: build-image-agents
	$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm --remove-orphans -e TEST_FILTER="$(TEST_FILTER)" unit-test-agents

check-deps:
	@if [ -z "${GITHUB_TOKEN}" ]; then echo "GITHUB_TOKEN not set. Export it with: export GITHUB_TOKEN=your_token"; exit 1; fi
	@curl -f http://localhost:11434/api/tags > /dev/null || (echo "Ollama not running"; exit 1)
	@curl -f -H "Authorization: token ${GITHUB_TOKEN}" https://api.github.com/user > /dev/null 2>&1 || (echo "GitHub token invalid or API unreachable"; exit 1)
	@$(MAKE) check-mcp-start || exit 1

# Run full integration tests with real LLM calls, requiring external dependencies (GITHUB_TOKEN, Ollama, MCP)
test-agents-integration: build-image-agents check-deps
	$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm --remove-orphans \
		-e TEST_FILTER="$(INTEGRATION_TEST_FILTER)" \
		-e OLLAMA_TIMEOUT="$(OLLAMA_TIMEOUT)" \
		integration-test-agents

test-agents-integration-fast: INTEGRATION_TEST_FILTER=--maxfail=1 -k "not slow"
test-agents-integration-fast: test-agents-integration

test-agents: lint-python test-agents-unit-mock test-agents-integration validate-test-suite

test: test-app test-agents

start-mcp:
	$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) up -d mcp-bridge

stop-mcp:
	$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) down mcp-bridge

check-mcp-start:
	@curl -f http://localhost:3000/health > /dev/null 2>&1 || (echo "MCP bridge not running, starting it..."; $(MAKE) start-mcp; sleep 5; curl -f http://localhost:3000/health > /dev/null 2>&1 || (echo "Failed to start MCP bridge"; exit 1))

check-mcp:
	@curl -f http://localhost:3000/health > /dev/null 2>&1 && echo "MCP bridge is running" || echo "MCP bridge is not running"
	@curl -f http://localhost:3000/servers > /dev/null 2>&1 && echo "MCP servers available" || echo "MCP servers not available"

# Verbose test runners
test-agents-unit-verbose: build-image-agents check-deps
	@echo "🚀 Starting verbose unit tests..."
	$(MAKE) create-logs
	@$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm --remove-orphans unit-test-agents-verbose 2>&1 | tee logs/$(shell date -u +%Y-%m-%d_%H%M%S)_unit_tests_verbose_output.txt; \
	exitcode=$${PIPESTATUS[0]}; \
	echo "🏁 Verbose unit tests completed with exit code: $$exitcode"; \
	exit $$exitcode

test-agents-integration-verbose: build-image-agents check-deps
	@echo "🚀 Starting verbose integration tests..."
	$(MAKE) create-logs
	@$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm --remove-orphans integration-test-agents-verbose 2>&1 | tee logs/$(shell date -u +%Y-%m-%d_%H%M%S)_integration_tests_verbose_output.txt; \
	exitcode=$${PIPESTATUS[0]}; \
	echo "🏁 Verbose integration tests completed with exit code: $$exitcode"; \
	exit $$exitcode
test-agents-unit-fail-verbose: build-image-agents check-deps
	@echo "🚀 Starting verbose unit tests with last failed..."
	@$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm --remove-orphans -e TEST_FILTER="--last-failed" unit-test-agents-verbose 2>&1 | tee logs/$(shell date -u +%Y-%m-%d_%H%M%S)_unit_tests_fail_verbose_output.txt; \
	exitcode=$${PIPESTATUS[0]}; \
	echo "🏁 Verbose unit fail tests completed with exit code: $$exitcode"; \
	exit $$exitcode

test-agents-integration-fail-verbose: build-image-agents check-deps
	@echo "🚀 Starting verbose integration tests with last failed..."
	@$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm --remove-orphans -e TEST_FILTER="--last-failed" integration-test-agents-verbose 2>&1 | tee logs/$(shell date -u +%Y-%m-%d_%H%M%S)_integration_tests_fail_verbose_output.txt; \
	exitcode=$${PIPESTATUS[0]}; \
	echo "🏁 Verbose integration fail tests completed with exit code: $$exitcode"; \
	exit $$exitcode

test-agents-unit-watch: build-image-agents
		$(MAKE) create-logs
		env HOST_UID=$(HOST_UID) HOST_GID=$(HOST_GID) $(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) up unit-test-agents-watch

test-agents-integration-watch: build-image-agents check-deps
	$(MAKE) create-logs
	env HOST_UID=$(HOST_UID) HOST_GID=$(HOST_GID) $(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) up integration-test-agents-watch

validate-test-suite: build-image-agents check-deps
	$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm validate-test-suite

check-secrets:
	$(CONTAINER_RUNTIME) run --rm -v $(PWD):/app trufflesecurity/trufflehog:latest filesystem /app --fail --only-verified

lint-python:
	$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm unit-test-agents bash -c "ruff check /app/src /app/tests && black --check /app/src /app/tests"

