DOCKER_COMPOSE_VERSION := v2.32.0
DOCKER_COMPOSE_PATH := .tools/docker-compose
DOCKER_COMPOSE_FILE := docker-compose-files/tools.yaml
REPO_NAME := obsidian-timestamp-utility
VERSION := $(shell node -p "require('./package.json').version")
TAG := $(VERSION)
IMAGE_NAME := $(REPO_NAME):$(TAG)

DOCKER_COMPOSE_FILE_PYTHON := docker-compose-files/agents.yaml

.PHONY: all build-image build-app test-app release changelog clean test-agents-unit test-agents-integration test-agents build-image-agents run-agentics

all: build-app test-app release

$(DOCKER_COMPOSE_PATH):
	mkdir -p .tools
	curl -L "https://github.com/docker/compose/releases/download/$(DOCKER_COMPOSE_VERSION)/docker-compose-$(shell uname -s | tr '[:upper:]' '[:lower:]')-$(shell uname -m)" -o $(DOCKER_COMPOSE_PATH)
	chmod +x $(DOCKER_COMPOSE_PATH)

build-image: $(DOCKER_COMPOSE_PATH)
	$(DOCKER_COMPOSE_PATH) -f $(DOCKER_COMPOSE_FILE) build --build-arg REPO_NAME=$(REPO_NAME)

build-app: build-image
	$(DOCKER_COMPOSE_PATH) -f $(DOCKER_COMPOSE_FILE) run --rm -e TAG=$(TAG) -e REPO_NAME=$(REPO_NAME) app /bin/bash -c "\
			npm install --loglevel=silly && \
			npm run build-package"

test-app: build-app
	$(DOCKER_COMPOSE_PATH) -f $(DOCKER_COMPOSE_FILE) run --rm -e TAG=$(TAG) -e REPO_NAME=$(REPO_NAME) app /bin/bash -c "\
			npm install --loglevel=silly && \
			npm test"

changelog: build-image
	$(DOCKER_COMPOSE_PATH) -f $(DOCKER_COMPOSE_FILE) run --rm -e TAG=$(TAG) -e REPO_NAME=$(REPO_NAME) app /bin/bash -c "\
			chmod +x /app/changelog.sh && \
			/app/changelog.sh"

release: clean build-app
	$(DOCKER_COMPOSE_PATH) -f $(DOCKER_COMPOSE_FILE) run --rm -e TAG=$(TAG) -e REPO_NAME=$(REPO_NAME) app /bin/bash -c "\
			chmod +x /app/release.sh && \
			find /app -name '*.sh' -exec dos2unix {} \; || { echo 'Error: dos2unix failed on some .sh files'; exit 1; } && \
			/app/release.sh"
	test -f release/release-timestamp-utility-$(TAG).zip || { echo "Release zip not created"; exit 1; }

clean:
	rm -rf .tools release dist

build-image-agents: $(DOCKER_COMPOSE_PATH)
	$(DOCKER_COMPOSE_PATH) -f $(DOCKER_COMPOSE_FILE_PYTHON) build

run-agentics: build-image-agents
	@if [ -z "$(ISSUE_URL)" ]; then \
			echo "Error: ISSUE_URL is not set. Usage: make run-agentics ISSUE_URL=<url>"; \
			exit 1; \
	fi
	$(DOCKER_COMPOSE_PATH) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm agentics python /app/src/agentics.py $(ISSUE_URL)

test-agents-unit: build-image-agents
	$(DOCKER_COMPOSE_PATH) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm unit-test-agents

test-agents-integration: build-image-agents
	$(DOCKER_COMPOSE_PATH) -f $(DOCKER_COMPOSE_FILE_PYTHON) run --rm integration-test-agents

test-agents: test-agents-unit test-agents-integration

test: test-app test-agents
