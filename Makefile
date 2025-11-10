# Variables
CONTAINER_RUNTIME := $(shell command -v nerdctl || command -v docker)
ifeq ($(CONTAINER_RUNTIME),)
$(error "Neither nerdctl nor docker is installed")
endif
CONTAINERD_CMD := ./containerd_wrapper.sh
DOCKER_COMPOSE_FILE := docker-compose-files/tools.yaml
REPO_NAME := obsidian-timestamp-utility
VERSION := $(shell node -p "require('./package.json').version")
TAG := $(VERSION)
IMAGE_NAME := $(REPO_NAME):$(TAG)
DOCKER_COMPOSE_FILE_PYTHON := docker-compose-files/agents.yaml

.PHONY: all build-image build-app test-app release changelog clean test-agents-unit test-agents-unit-last-failed test-agents-integration test-agents build-image-agents run-agentics generate-requirements

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
						chmod +x /app/changelog.sh && \
						/app/changelog.sh"

release: clean build-app
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE) run --rm -e TAG=$(TAG) -e REPO_NAME=$(REPO_NAME) app /bin/bash -c "\
						chmod +x /app/release.sh && \
						find /app -name '*.sh' -exec dos2unix {} \; || { echo 'Error: dos2unix failed on some .sh files'; exit 1; } && \
						/app/release.sh"
		test -f release/release-timestamp-utility-$(TAG).zip || { echo "Release zip not created"; exit 1; }

clean:
		rm -rf release dist

build-generate-requirements:
		$(CONTAINERD_CMD) build -t pip-requirements -f docker-files/pip-requirements/Dockerfile .

generate-requirements: build-generate-requirements
		$(CONTAINERD_CMD) run --rm -v $(PWD)/agents/agentics:/app pip-requirements

build-image-agents:
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) build

run-agentics: build-image-agents
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm agentics

test-agents-unit: build-image-agents
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm -e TEST_FILTER="$(TEST_FILTER)" unit-test-agents

test-agents-unit-last-failed: build-image-agents
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm -e TEST_FILTER="--last-failed" unit-test-agents

test-agents-integration: build-image-agents
		$(CONTAINERD_CMD) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm integration-test-agents

test-agents: test-agents-unit test-agents-integration

test: test-app test-agents
