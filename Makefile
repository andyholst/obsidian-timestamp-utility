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

HOST_UID  := $(shell id -u)
HOST_GID  := $(shell id -g)
export HOST_UID HOST_GID

# Ollama (local LLM that generates the TS code + TS tests)
OLLAMA_MODEL      ?= sorc/qwen3.5-claude-4.6-opus:9b
OLLAMA_CODE_MODEL ?= sorc/qwen3.5-claude-4.6-opus:9b
OLLAMA_HOST       ?= http://localhost:11434

ISSUE_URL         ?= https://github.com/andyholst/obsidian-timestamp-utility/issues/20
TEST_FILTER       ?=
INTEGRATION_TEST_FILTER ?=
OLLAMA_TIMEOUT    ?= 300
TYPE              ?=
CHANGE            ?= uuid-modal-agentic-generation
export TEST_FILTER INTEGRATION_TEST_FILTER OLLAMA_TIMEOUT TYPE OLLAMA_HOST CHANGE

# docker_run: run a `docker compose ... run` command, providing a PTY when needed.
# nerdctl's `compose run` HARDCODES `--interactive --tty`, so the container needs a
# real console; without one it dies with "provided file is not a console". When stdout
# IS a terminal (interactive shell, or the loop runner's `setsid script` wrapper) we run
# the command PLAIN -- this avoids ever NESTING PTYs (which triggers a SIGSTOP deadlock
# under job control). When stdout is NOT a tty (CI / piped / redirected), we wrap in
# `script -qec` to synthesize a console. `script` propagates the command's exit code.
define docker_run
	@if [ -t 1 ]; then $(1); else script -qec "$(1)" /dev/null; fi
endef

DOCKER_SOCK := $(shell \
	if [ -S /var/run/docker.sock ]; then echo /var/run/docker.sock; \
	elif [ -S /run/containerd/containerd.sock ]; then echo /run/containerd/containerd.sock; \
	elif [ -S $(XDG_RUNTIME_DIR)/containerd/containerd.sock ]; then echo $(XDG_RUNTIME_DIR)/containerd/containerd.sock; \
	elif [ -S $(XDG_RUNTIME_DIR)/containerd-rootless/api.sock ]; then echo $(XDG_RUNTIME_DIR)/containerd-rootless/api.sock; \
	else echo ""; fi)

.PHONY: help all \
        build-app test-app changelog release \
        lint-python test-validator format \
        test-agents-unit test-agents-unit-mock test-agents-integration test-agents-integration-fast test-agents-e2e \
        test-agents test-agents-real verify-agentics-after-run \
        run-agentics phase7-archive b9-perms record-work squash-commits openspec-new \
        check-deps check-github check-issue-url check-ollama check-secrets \
        fix-perms create-logs \
        collect-tests collect-executed generate-requirements \
        stop-containers \
        clean clean-cache clean-logs clean-oci \
        loop-harness loop-unit loop-integration loop-build-app loop-test-app loop-verify loop-tasks \
        squash-commits \
        bump-version release-notes tag-release loop-release check-released release bump-local release-prep

.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "obsidian-timestamp-utility Makefile (docker compose, no Dagger)"
	@echo "Core dev: build-app test-app run-agentics test"
	@echo "=================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-35s\033[0m %s\n", $$1, $$2}'

all: build-app test-app release ## Full pipeline

# ---- Plugin (TS) build/test via containers/npm ----

build-app: b9-perms ## Build Obsidian plugin via docker compose (containers/npm)
	@echo "Building plugin (npm run build) via containers/npm..."
	docker compose -f docker-compose-files/tools.yaml run --rm app npm run build
	@echo "Build complete"

test-app: b9-perms ## Test the built plugin via docker compose (containers/npm)
	@echo "Running jest via containers/npm..."
	docker compose -f docker-compose-files/tools.yaml run --rm app npm test
	@echo "=== Plugin test output above ==="

validate-ts: ## Fast TypeScript validation (runs tsc directly)
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

validate-tests: ## Fast test validation (runs jest directly)
	@echo "Running test validation..."
	@npx jest --no-cache --passWithNoTests 2>&1
	@echo "Test validation complete"

changelog: ## Generate CHANGELOG.md (git_chglog via the unit-test-agents service)
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents python -m git_chglog -o CHANGELOG.md) || echo "changelog skipped"

release: clean build-app ## Create release + ZIP check
	@if [ -z "$(TAG)" ]; then echo "Error: TAG could not be determined from package.json" >&2; exit 1; fi
	@mkdir -p release
	@cp -r dist manifest.json release/ 2>/dev/null || true
	@cd release && zip -r ../$(REPO_NAME)-$(TAG).zip . >/dev/null
	@echo "Release zip: $(REPO_NAME)-$(TAG).zip"

lint-python: ## Run ruff linting on Python code via compose
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents ruff check agents/agentics/src) || echo "ruff reported issues"

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

format: ## Format Python code with ruff via compose
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents ruff format agents/agentics/src) || true

# ---- Agentic (Python) tests via containers/agents ----

test-agents-unit: ## Unit tests for agents (Ollama)
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents)
	@echo "=== Unit test results ==="

test-agents-unit-mock: ## Mocked unit tests (fast, no Ollama)
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e TEST_FILTER=$(TEST_FILTER) unit-test-agents python -m pytest tests/unit/ -q)
	@echo "=== Mock unit test output above ==="

test-agents-integration: ## Full integration tests (needs GITHUB_TOKEN + Ollama)
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e GITHUB_TOKEN=$(GITHUB_TOKEN) -e TEST_FILTER='$(INTEGRATION_TEST_FILTER)' integration-test-agents)
	@echo "=== Integration test results ==="

test-agents-integration-fast: INTEGRATION_TEST_FILTER = --maxfail=1 -k not slow ## Fast integration tests (fail fast, skip slow)
test-agents-integration-fast: test-agents-integration

test-agents-e2e: INTEGRATION_TEST_FILTER = -m e2e ## End-to-end tests only
test-agents-e2e: test-agents-integration

test-agents: lint-python test-agents-unit-mock test-agents-integration ## All agent tests
test-agents-real: lint-python test-agents-unit test-agents-integration ## Agent tests on REAL logic (no mocks for units; real Ollama/GitHub calls)
# Collection guard (audit-mcp-slim-refactor-integrity 4.2): fail fast if any test file has a
# dangling import / collection error — a slim-refactor that orphans a symbol must surface here
# instead of reporting a cached "green". Runs hermetic (no Ollama) and is non-zero on any error.
test-agents-collect: ## CI guard: pytest --collect-only for unit + integration; fails on any collection error
	@echo "=== Collection guard: unit ==="
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents python -m pytest tests/unit/ --collect-only -q)
	@echo "=== Collection guard: integration ==="
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm integration-test-agents python -m pytest tests/integration/ --collect-only -q)
	@echo "=== Collection guard: clean (0 errors) ==="
verify-agentics-after-run: ## After run-agentics: re-run agentic suite to prove refactored Python is still valid/in-sync
	@echo "Re-running agentic unit + integration (real) after run-agentics..."
	@$(MAKE) test-agents-unit
	@$(MAKE) test-agents-integration
	@echo "=== Agentic suite green after run-agentics ==="
test: test-app test-agents ## All tests (app + agents)

# ---- Agentic code generation (OpenSpec-driven, local, Ollama) ----

run-agentics: b9-perms ## Run AI agentics on a LOCAL OpenSpec change (CHANGE=<name>); no GitHub fetch, no MCP
	@echo "Running agentics with Ollama model: $(OLLAMA_MODEL)"
	@echo "OpenSpec change: $(CHANGE)"
	@test -n "$(CHANGE)" || { echo "ERROR: set CHANGE=<openspec-change-name> (e.g. make run-agentics CHANGE=uuid-modal-agentic-generation)"; exit 1; }
	@# ---- BACK UP BEFORE GENERATING (timestamped safety net) ----
	@mkdir -p backups
	@TS=$$(date +%Y%m%d-%H%M%S); \
	for f in src/main.ts src/__tests__/main.test.ts; do \
		if [ -f "$$f" ]; then \
			cp -p "$$f" "backups/$$(basename $$f).$$TS.bak" && echo "BACKUP: $$f -> backups/$$(basename $$f).$$TS.bak"; \
		else \
			echo "WARN: $$f not present, nothing to back up"; \
		fi; \
	done
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e CHANGE=$(CHANGE) -e GITHUB_TOKEN=$(GITHUB_TOKEN) -e OLLAMA_HOST=$(OLLAMA_HOST) -e OLLAMA_REASONING_MODEL=$(OLLAMA_MODEL) -e OLLAMA_CODE_MODEL=$(OLLAMA_CODE_MODEL) -e PROJECT_ROOT=/project agentics python -m prod.agentics openspec:$(CHANGE))
	@echo "=== Agentics run complete ==="
	@ls -la src/main.ts src/__tests__/main.test.ts 2>/dev/null || echo "Note: generated files may be in a different location"
	@# ---- OMISSION GUARD (contract-aware, per bug 6.2): a shrink is only a genuine ----
	@#      omission if the generated file DROPPED the contract's command id. A feature
	@#      switch legitimately produces a different-sized file (e.g. greetings test <
	@#      uuid test), so pure byte-size comparison against the previous run's backup is
	@#      a false positive. If the new contract command id is present, it is a successful
	@#      generation — never restore. Only restore when the command id is MISSING AND the
	@#      file shrank (LLM dropped existing logic — the real B6/B11 omission case).
	@TS=$$(ls -1 backups/*.bak 2>/dev/null | head -1 | sed -E 's/.*\.([0-9]{8}-[0-9]{6})\.bak/\1/'); \
	CMD_ID=$$(grep -rhoE "id: '[^']+'" openspec/changes/$(CHANGE)/ 2>/dev/null | head -1 | sed -E "s/id: '([^']+)'/\1/"); \
	for f in src/main.ts src/__tests__/main.test.ts; do \
		bak=$$(ls -1 backups/$$(basename $$f).*.bak 2>/dev/null | tail -1); \
		if [ -f "$$f" ] && [ -n "$$bak" ]; then \
			before=$$(wc -c < "$$bak"); after=$$(wc -c < "$$f"); \
			if [ "$$after" -lt "$$before" ]; then \
				if [ -n "$$CMD_ID" ] && grep -q "$$CMD_ID" "$$f"; then \
					echo "OK: $$f shrank ($$before -> $$after) but contract command '$$CMD_ID' present — legitimate feature switch, NOT an omission."; \
				else \
					echo "OMISSION DETECTED: $$f shrank ($$before -> $$after bytes) and contract command '$$CMD_ID' missing. Restoring backup."; \
					cp -p "$$bak" "$$f"; \
					echo "ACTION: investigate why agentic code dropped content (code_integrator / code_extractor / export_name assembly) before re-running."; \
				fi; \
			else \
				echo "OK: $$f size $$before -> $$after bytes (no omission)."; \
			fi; \
		fi; \
	done

# ---- Loop-harness stage: run the harness/loop-engineering verification gates in the
#      EXACT order AGENTS.md prescribes, via `make loop-harness`. SEVEN stages (a collection
#      guard + six gates), AGENTS.md Phase 6 + B1/B3/B7.1/B17:
#        0. collect guard     (loop-collect)   -- hermetic collection guard (fail fast on dangling imports), audit-mcp-slim-refactor-integrity 4.2
#        1. unit tests        (loop-unit)       -- Fast/Unit gate FIRST (hermetic, no Ollama)
#        2. unit-real tests   (loop-unit-real)  -- REAL agent unit tests (live Ollama, no mocks)
#        3. e2e tests         (loop-e2e)        -- the 3 standing e2e gates (ticket20+ticket22+greetings), B1/B3
#        4. integration tests (loop-integration) -- broad agentic integration suite (B17)
#        5. build-app         (loop-build-app)  -- tsc/rollup of the plugin, must exit 0
#        6. test-app          (loop-test-app)   -- jest of the plugin, must pass
#      Each stage fails the whole run if it fails (no silent green). No git commit/push
#      (B4/B14). Optional post-check: `make loop-verify CHANGE=<name>` runs openspec
#      (B4/B14). Optional post-check: `make loop-verify CHANGE=<name>` runs openspec
#      validate + status for the active change.
loop-collect: ## Loop gate 0/7: hermetic collection guard (fail fast on dangling imports)
	@echo "=== LOOP-HARNESS [collect] collection guard (no dangling imports) ==="
	@$(MAKE) test-agents-collect

loop-unit: ## Loop gate 1/7: hermetic unit tests (fast, no Ollama/GitHub)
	@echo "=== LOOP-HARNESS [1/6] unit tests (mocked, hermetic) ==="
	@$(MAKE) test-agents-unit-mock

loop-unit-real: ## Loop gate 2/7: REAL agent unit tests (live Ollama, no mocks)
	@echo "=== LOOP-HARNESS [2/6] real agent unit tests (Ollama) ==="
	@$(MAKE) test-agents-unit

loop-e2e: ## Loop gate 3/7: standing e2e gates (ticket20 + ticket22 + greetings)
	@echo "=== LOOP-HARNESS [3/6] e2e gates (-m e2e) ==="
	@$(MAKE) test-agents-e2e

loop-integration: ## Loop gate 4/7: broad agentic integration suite (B17) — excludes e2e (its own stage) and slow full-pipeline tests
	@echo "=== LOOP-HARNESS [4/6] integration suite (-m 'integration and not e2e and not slow') ==="
	@$(MAKE) test-agents-integration INTEGRATION_TEST_FILTER="-m 'integration and not e2e and not slow'"

loop-build-app: ## Loop gate 5/7: build the Obsidian plugin (tsc/rollup, exit 0)
	@echo "=== LOOP-HARNESS [5/6] build-app ==="
	@$(MAKE) build-app

loop-test-app: ## Loop gate 6/7: run jest on the plugin
	@echo "=== LOOP-HARNESS [6/6] test-app ==="
	@$(MAKE) test-app

loop-harness: ## Full loop-harness: SINGLE source of truth = scripts/run-loop-harness.sh.
	@# This target delegates to the script so the per-stage timeouts + docker-kill
	@# logic are ALWAYS applied (never a bare `make` chain that can hang forever).
	@# The script calls back into these same `loop-*` targets, so what runs is
	@# identical whether you invoke `make loop-harness` or the script directly.
	@bash scripts/run-loop-harness.sh
	@echo "=== LOOP-HARNESS COMPLETE: all gates green in order (collect -> unit -> unit-real -> e2e -> integration -> build-app -> test-app) ==="

loop-trigger: ## B20 mandatory pre-flight: run the loop gate (scripts/run-loop-harness.sh) before claiming done
	@bash scripts/run-loop-harness.sh

loop-verify: ## Loop verify: openspec validate + status for CHANGE (run after loop-harness)
	@test -n "$(CHANGE)" || { echo "WARN: set CHANGE=<openspec-change-name> to verify a change; skipping."; exit 0; }
	@echo "=== LOOP-VERIFY: openspec validate $(CHANGE) ==="
	@openspec validate $(CHANGE)
	@echo "=== LOOP-VERIFY: openspec status --change $(CHANGE) ==="
	@openspec status --change $(CHANGE)

# ---- Delivery gap fix: pull verified worktree TS back onto the active branch ----
#
# The agentic pipeline generates + verifies TS inside a git WORKTREE (feat/<name>) and the
# harness previously STOPPED there -- the verified code never reached the branch it was
# supposed to land on. This target closes that gap (behaviour mandated by AGENTS.md B12):
# it copies the WORKTREE's verified src/main.ts + src/__tests__/main.test.ts into the CURRENT
# branch's working tree. It does NOT commit/push (B4) -- that remains a deliberate human step.
# Usage: make deliver-change CHANGE=uuid-modal-agentic-generation
deliver-change: ## Pull verified worktree TS (src/main.ts + main.test.ts) onto the current branch
	@test -n "$(CHANGE)" || { echo "ERROR: set CHANGE=<openspec-change-name>"; exit 1; }
	@WT=worktrees/$(CHANGE); \
	if [ ! -d "$$WT" ]; then echo "ERROR: worktree $$WT not found"; exit 1; fi; \
	for f in src/main.ts src/__tests__/main.test.ts; do \
		if [ -f "$$WT/$$f" ]; then \
			cp -p "$$WT/$$f" "$$f" && echo "DELIVERED: $$WT/$$f -> $$f"; \
		else \
			echo "WARN: $$WT/$$f not present, skipped"; \
		fi; \
	done
	@echo "=== Delivered verified TS to current branch ($(shell git branch --show-current)). Review + commit manually. ==="

# ---- Phase 7: archive gate with durable E2E + no-commit guards ----
#
# DURABLE AGENT BEHAVIOURS (see AGENTS.md / hermes/skills/openspec-loop-harness.md):
#   (B1) E2E tests that read a change's tasks.md must NEVER be removed when a change is
#        archived/done. The standing harness is
#        agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py
#   (B4) The pipeline MUST NEVER commit/push when generated task code already exists.
#        This guard only archives the SPEC (openspec archive) -- it never `git add`,
#        `git commit`, or `git push`. Committing/pushing is a SEPARATE, explicit human step.
phase7-archive: ## Archive an OpenSpec change (spec only) + assert durable E2E present
	@test -n "$(CHANGE)" || { echo "ERROR: set CHANGE=<openspec-change-name>"; exit 1; }
	@# B16 (enforce-task-completion-gate): FAILS-CLOSED. Refuse to archive a change
	@#      with open `- [ ]` tasks. A half-done change must never be silently archived.
	@echo "B16: checking for open tasks in $(CHANGE)..."
	@python3 -c "import sys; sys.path.insert(0, 'agents/agentics/src'); from openspec_loader import assert_no_open_tasks; assert_no_open_tasks('$(CHANGE)')" || { echo "FAIL(B16): $(CHANGE) has open tasks (see above). Tick them in tasks.md, then re-run."; exit 1; }
	@# B1: the persistent E2E harness must still exist -- never deleted on archive.
	@test -f agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py || { echo "FAIL(B1): persistent e2e harness missing -- do NOT remove it on archive."; exit 1; }
	@# B4: refuse to touch git. This target archives ONLY the openspec spec; it does
	@#      NOT commit or push. (User commits the generated TS/tests separately & deliberately.)
	@echo "Archiving spec for $(CHANGE) (openspec archive -y -- spec only, no git commit/push)..."
	@openspec archive -y $(CHANGE)
	@echo "DONE: spec archived. No git commit/push performed. Verify + commit TS/tests manually if intended."

# ---- Phase 7: scriptable work-log entry (replaces the never-created `record-work` skill) ----
#
# AGENTS.md Phase 7 says "Call the record-work skill -> write agent-wiki/YYYY-MM-DD-<name>.md".
# No such skill exists, so this target runs scripts/record-work.py, which collects the change's
# proposal/tasks/specs + openspec status/validate + git branch/commit, asks the project-manager
# Hermes CLI (`hermes -z`, same pattern as the `squash-commits` target) to draft the prose, then writes
# agent-wiki/YYYY-MM-DD-<change>.md and updates agent-wiki/index.md. b9-perms is a prerequisite so
# the container write targets are world-writable under rootless nerdctl. No git commit/push (B4/B14).
# ---- OpenSpec change scaffolding harness (B15: change dir created via the real `openspec` CLI) ----
#
# Wraps scripts/scaffold-openspec-change.sh, which calls `openspec new change <NAME>` (the exact
# CLI step a human runs — never hand-writes the directory) then seeds proposal.md / tasks.md /
# specs/<CAPABILITY>/spec.md from a template and runs `openspec validate`. b9-perms is a prerequisite
# so the write targets are world-writable under rootless nerdctl. No git commit/push (B4/B14).
# Usage: make openspec-new NAME=<kebab-name> [DESC="..."] [GOAL="..."] [CAPABILITY=<cap>]
openspec-new: b9-perms ## Scaffold an OpenSpec change via the openspec CLI + seeded template (NAME required)
	@if [ -z "$(NAME)" ]; then echo "ERROR: NAME is required. Run: make openspec-new NAME=<kebab-name> [CAPABILITY=<cap>] [DESC=...] [GOAL=...]"; echo "--- script usage ---"; bash scripts/scaffold-openspec-change.sh --help; exit 1; fi
	@echo "=== OPENSPEC-NEW: scaffolding change $(NAME) ==="
	@bash scripts/scaffold-openspec-change.sh --name $(NAME) $(if $(DESC),--desc "$(DESC)",) $(if $(GOAL),--goal "$(GOAL)",) $(if $(CAPABILITY),--capability $(CAPABILITY),)
	@echo "=== OPENSPEC-NEW complete: review openspec/changes/$(NAME)/ ==="

record-work: b9-perms ## Phase 7 work-log: write agent-wiki/YYYY-MM-DD-<change>.md via scripts/record-work.py
	@test -n "$(CHANGE)" || { echo "ERROR: set CHANGE=<openspec-change-name> (e.g. make record-work CHANGE=uuid-modal-agentic-generation)"; exit 1; }
	@echo "=== RECORD-WORK: agent-wiki entry for $(CHANGE) ==="
	@python3 scripts/record-work.py --change $(CHANGE) $(if $(DATE),--date $(DATE),)
	@echo "=== RECORD-WORK complete: review agent-wiki/$(shell date +%Y-%m-%d)-$(CHANGE).md ==="

loop-tasks: ## Loop visibility: list open/done task counts for every active change
	@echo "=== LOOP-TASKS: open/done per active change (changes with open tasks first) ==="
	@for d in $$(ls -1 openspec/changes 2>/dev/null); do \
		if [ "$$d" = "archive" ] || [ "$$d" = ".gitkeep" ]; then continue; fi; \
		tf=openspec/changes/$$d/tasks.md; \
		if [ ! -f "$$tf" ]; then echo "  $$d   (no tasks.md)"; continue; fi; \
		open=$$(grep -cE '^- \[[ ]\]' $$tf); \
		done=$$(grep -cE '^- \[[xX]\]' $$tf); \
		printf "  %-40s open=%-3s done=%-3s\n" "$$d" "$$open" "$$done"; \
	done
	@echo "=== run 'make phase7-archive CHANGE=<name>' only when open=0 ==="

squash-commits: ## Squash ALL commits ahead of `main` into ONE thoroughly-typed Conventional commit (Hermes, project-manager). The FIRST line MUST be `type(scope): subject` (type in feat|fix|docs|refactor|perf|test|chore|build|ci|style|revert) so the changelog sections and the version bump are tagged accordingly. NO push (B14).
	@# Diff base is `main` (the real branch origin), NOT the loose upstream.
	@# Hermes receives the changed-file list + diff-stat vs `main` and must
	@# write a THOROUGH body describing what the substantive files
	@# ACTUALLY do (behaviour), not meta commentary about the commit tool.
	@# CRITICAL (release-automation): the FIRST line is the Conventional-Commits
	@# tag (e.g. `feat(loop): ...`, `fix(agentics): ...`, `docs(readme): ...`).
	@# The changelog sections (chglog/config.yml) and `bump-version` PART are
	@# derived from this type, so it MUST start with `^(feat|fix|docs|refactor
	@# |perf|test|chore|build|ci|style|revert)(\(.*\))?:\s`. Fail-closed otherwise.
	@MAIN=$$(git rev-parse --verify origin/main 2>/dev/null || git rev-parse --verify main 2>/dev/null || echo ""); \
	if [ -z "$$MAIN" ]; then echo "COMMIT: no 'main' ref found -- aborting."; exit 1; fi; \
	AHEAD=$$(git rev-list --count $$MAIN..HEAD 2>/dev/null || echo 0); \
	if [ "$$AHEAD" = "0" ] && [ -z "$$(git diff HEAD --name-only)" ]; then echo "COMMIT: nothing ahead of main and tree clean -- nothing to squash/commit."; exit 0; fi; \
	echo "COMMIT: $$AHEAD commit(s) ahead of main -- squashing into one."; \
	git reset --soft $$MAIN; \
	git add -A; \
	FILES=$$(git diff --cached --name-only $$MAIN); \
	STAT=$$(git diff --stat $$MAIN | tail -40); \
	echo "COMMIT: $$AHEAD commits squashed. Changed files vs main:"; echo "$$FILES"; \
	echo "COMMIT: asking Hermes (profile=project-manager) for a THOROUGH, TYPED Conventional message..."; \
	hermes profile use project-manager >/dev/null 2>&1 || true; \
	PROMPT="You are writing ONE git commit message in Conventional Commits / Angular style for a branch being squashed into a single commit. RULE 1 (mandatory): the FIRST line is EXACTLY 'type(scope): subject' where type is ONE of: feat, fix, docs, refactor, perf, test, chore, build, ci, style, revert; scope is the area (e.g. loop, agentics, readme, release); subject is imperative, <=72 chars, no trailing period. RULE 2: then a blank line, then a THOROUGH human-readable body (wrapped ~72 cols) describing WHAT the changed code now does and WHY, grounded in the actual files below -- not meta commentary about the commit command. Cover substantive areas: the OpenSpec loop-harness engineering (deterministic code_integrator floor, B1-B21 durable behaviours), agentic pipeline changes, Makefile / docker-compose / Containerfile changes, OpenSpec specs merged, and any test/behaviour fixes. Be specific. Output ONLY the raw commit message (title + blank + body), no code fences, no preamble. CHANGED FILES vs main:$$(printf '\n%s' $$FILES) DIFF STAT vs main:$$(printf '\n%s' $$STAT)"; \
	MSG=$$(hermes -z "$$PROMPT" 2>/dev/null); \
	if [ -z "$$MSG" ]; then echo "COMMIT: Hermes returned no message -- aborting (no empty commit)."; git reset --quit $$MAIN >/dev/null 2>&1 || true; exit 1; fi; \
	FIRST=$$(printf '%s' "$$MSG" | head -1); \
	if ! printf '%s' "$$FIRST" | grep -qE '^(feat|fix|docs|refactor|perf|test|chore|build|ci|style|revert)(\([^)]*\))?:\s'; then \
		echo "COMMIT: FAIL-CLOSED -- first line is not a typed Conventional commit: '$$FIRST'"; \
		echo "COMMIT: refusing to create an untyped commit (changelog + bump need the type)."; \
		git reset --quit $$MAIN >/dev/null 2>&1 || true; exit 1; \
	fi; \
	git commit -m "$$MSG" && echo "COMMIT: created one TYPED Conventional commit (not pushed -- B14). Review with 'git show'."

# ---- Release automation (post-green loop-engineering stage) ----
#
# SINGLE COMMAND for the user: `make release` bumps the Obsidian version, squashes a TYPED
# Conventional commit, regenerates the sectioned CHANGELOG, refreshes the README release-notes
# block, and creates a LOCAL tag. `loop-release` is the loop-facing variant (same steps, guarded
# on generated-TS changes). Both are guarded by `check-released` so a version already published to
# the GitHub project repo is NEVER bumped/tagged again.
#
# Order (single command `make release`):
#   1. check-released -- abort if CURRENT version is already tagged on GitHub (tolerant X / vX)
#   2. bump-version  -- Obsidian way: package.json + manifest.json + versions.json
#   3. squash-commits-- one TYPED Conventional commit (type drives changelog + bump)
#   4. changelog     -- regenerate CHANGELOG.md (git_chglog, SECTIONED by commit type)
#   5. release-notes -- refresh the README "Release / Changelog" block (mirrors sections)
#   6. tag-release   -- local `git tag v<version>` (NO push, B14)
# The squashed commit's Conventional type is the single source of truth for BOTH the changelog
# sections and the version-bump PART, so the commit is "tagged accordingly" before it is ever written.
PART ?= patch

check-released: ## Guard: FAIL if the CURRENT package.json version is already released on GitHub (remote tag <ver> or v<ver>), OR if it does NOT advance past the latest released version (no semver gap). FAIL-CLOSED if gh/network unavailable.
	@command -v node >/dev/null 2>&1 || { echo "CHECK-RELEASED: node required -- aborting."; exit 1; }
	@VER=$$(node -p "require('./package.json').version"); \
	echo "CHECK-RELEASED: current version = $$VER"; \
	if ! command -v gh >/dev/null 2>&1; then echo "CHECK-RELEASED: gh CLI not found -- REFUSING (cannot verify release state)."; exit 1; fi; \
	echo "CHECK-RELEASED: querying origin for released tags..."; \
	REMOTE=$$(git ls-remote --tags --refs origin 2>/dev/null | awk '{print $$2}' | sed 's#refs/tags/##' | sed 's/^v//' || true); \
	if echo "$$REMOTE" | grep -qx "$$VER"; then echo "CHECK-RELEASED: version $$VER is ALREADY RELEASED on GitHub -- bump BLOCKED. Release it (git push) or fix package.json before bumping."; exit 1; fi; \
	LATEST=$$(echo "$$REMOTE" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$$' | sort -t. -k1,1n -k2,2n -k3,3n | tail -1); \
	echo "CHECK-RELEASED: latest released version on GitHub = $${LATEST:-<none>}"; \
	if [ -n "$$LATEST" ]; then \
		ADV=$$(awk -F. -v c="$$VER" -v l="$$LATEST" 'BEGIN{split(c,a,".");split(l,b,".");for(i=1;i<=3;i++){if(a[i]>b[i]){print 0;exit};if(a[i]<b[i]){print 1;exit}}print 1}'); \
		if [ "$$ADV" != "0" ]; then echo "CHECK-RELEASED: $$VER does NOT advance past latest released $$LATEST (no semver gap) -- bump BLOCKED."; exit 1; fi; \
	fi; \
	echo "CHECK-RELEASED: $$VER is NOT released and advances past $${LATEST:-<none>} -- OK to bump."

bump-version: ## Bump the Obsidian plugin version (Obsidian way): package.json + manifest.json + append versions.json. PART=patch|minor|major (default patch). ONLY when new plugin TS exists in src/main.ts vs origin/main.
	@command -v node >/dev/null 2>&1 || { echo "BUMP: node required -- aborting."; exit 1; }
	@command -v jq  >/dev/null 2>&1 || { echo "BUMP: jq required -- aborting."; exit 1; }
	@# Guard: only bump when new generated plugin TS actually exists in src/main.ts vs origin/main
	@# (the committed baseline the branch forked from). Fall back to HEAD if origin/main is absent.
	@if [ ! -f src/main.ts ]; then echo "BUMP: src/main.ts missing -- refusing to bump (no plugin code)."; exit 1; fi; \
	BASE=$$(git rev-parse --verify origin/main 2>/dev/null || echo "HEAD"); \
	if git diff --quiet $$BASE -- src/main.ts && [ -z "$$(git ls-files --others --exclude-standard src/main.ts)" ]; then \
		echo "BUMP: no new plugin TS code in src/main.ts vs $$BASE -- refusing to bump (nothing to release)."; exit 1; \
	fi; \
	echo "BUMP: new plugin TS detected in src/main.ts vs $$BASE -- proceeding with version bump."; \
	OLD=$$(node -p "require('./package.json').version"); \

	if [ "$$PART" != "patch" ] && [ "$$PART" != "minor" ] && [ "$$PART" != "major" ]; then echo "BUMP: PART must be patch|minor|major (got '$$PART')"; exit 1; fi; \
	IFS='.' read -r MAJ MIN PAT <<< "$$OLD"; \
	if [ "$$PART" = "major" ]; then MAJ=$$((MAJ+1)); MIN=0;  PAT=0; \
	elif [ "$$PART" = "minor" ]; then MIN=$$((MIN+1)); PAT=0; \
	else PAT=$$((PAT+1)); fi; \
	NEW="$$MAJ.$$MIN.$$PAT"; \
	echo "BUMP: $$OLD -> $$NEW (PART=$$PART)"; \
	node -e "const f='package.json';const j=require('./'+f);j.version='$$NEW';require('fs').writeFileSync(f,JSON.stringify(j,null,2)+'\n');"; \
	node -e "const f='manifest.json';const j=require('./'+f);j.version='$$NEW';require('fs').writeFileSync(f,JSON.stringify(j,null,2)+'\n');"; \
	TMP=$$(mktemp); \
	jq --arg v "$$NEW" --arg m "$$(node -p "require('./manifest.json').minAppVersion")" '. + {$$v:$$m}' versions.json > "$$TMP" && mv "$$TMP" versions.json; \
	echo "BUMP: versions.json now has entry \"$$NEW\"."; \
	echo "BUMP: done. Review package.json / manifest.json / versions.json, then commit via 'make squash-commits'."

release-notes: ## Refresh the README "Release / Changelog" block to the current version, categorized by commit type (mirrors the changelog sections).
	@command -v node >/dev/null 2>&1 || { echo "RELNOTES: node required -- aborting."; exit 1; }
	@python3 scripts/update-release-notes.py README.md

tag-release: ## Create a LOCAL git tag v<version> (NO push -- B14). Run AFTER squash-commits.
	@command -v node >/dev/null 2>&1 || { echo "TAG: node required -- aborting."; exit 1; }
	@VER=$$(node -p "require('./package.json').version"); \
	TAG="v$$VER"; \
	if git rev-parse "$$TAG" >/dev/null 2>&1; then echo "TAG: $$TAG already exists -- skipping."; exit 0; fi; \
	git tag -a "$$TAG" -m "Release $$VER"; \
	echo "TAG: created local tag $$TAG (NOT pushed -- B14). Push deliberately with 'git push origin $$TAG'."; \
	echo "TAG: verify with 'git show $$TAG'."

release-prep: check-released ## LOCAL release prep (publish happens in CI): bump (Obsidian way) -> typed squash -> sectioned changelog -> README release-notes -> local tag. Refuses if current version already released on GitHub. NO push (B14) -- the actual GitHub release is done by .github/workflows/release.yml on merge to main.
	@echo "=== RELEASE-PREP: local release prep (guarded) ==="; \
	$(MAKE) bump-version PART=$(PART); \
	$(MAKE) squash-commits; \
	$(MAKE) changelog; \
	$(MAKE) release-notes; \
	$(MAKE) tag-release; \
	echo "=== RELEASE-PREP COMPLETE: bump + squashed typed commit + changelog + release-notes + local tag. The GITHUB RELEASE is cut by CI (.github/workflows/release.yml) when you merge to main / push the tag. NO push here (B14). ==="

loop-release: ## Post-green release stage: guard (generated TS changed + not already released) -> bump -> squash -> changelog -> release-notes -> local tag. NO push.
	@echo "=== LOOP-RELEASE: post-green release stage ==="; \
	CHANGED=0; for f in src/main.ts src/__tests__/main.test.ts; do \
		if [ -f "$$f" ] && ! git diff --quiet HEAD -- "$$f"; then CHANGED=1; echo "LOOP-RELEASE: $$f changed vs HEAD"; fi; \
	done; \
	if [ "$$CHANGED" = "0" ]; then echo "LOOP-RELEASE: no generated TS changed vs HEAD -- NO-OP (no version bump, no tag)."; exit 0; fi; \
	echo "LOOP-RELEASE: generated TS changed -> running guarded release."; \
	$(MAKE) check-released; \
	$(MAKE) bump-version PART=patch; \
	$(MAKE) squash-commits; \
	$(MAKE) changelog; \
	$(MAKE) release-notes; \
	$(MAKE) tag-release; \
	echo "=== LOOP-RELEASE COMPLETE: bump + squashed typed commit + changelog + release-notes + local tag. NO push (B14). ==="

bump-local: check-released ## LOCAL-ONLY: bump the Obsidian version + create a LOCAL tag, WITHOUT the full release flow (no squash-commits, no changelog, no release-notes, no push). For advancing the version locally.
	@echo "=== BUMP-LOCAL: bump version + local tag only (no squash/changelog/publish) ==="; \
	$(MAKE) bump-version PART=$(PART); \
	$(MAKE) tag-release; \
	echo "=== BUMP-LOCAL COMPLETE: version bumped (Obsidian way) + local tag. NO commit squash, NO changelog, NO push (B14). ==="

# ---- Checks ----

check-deps: check-ollama check-issue-url ## Verify external dependencies
check-github: ## Validate GitHub token (only needed for integration tests)
	@if [ -z "$(GITHUB_TOKEN)" ]; then echo "Error: GITHUB_TOKEN is required for integration tests" >&2; exit 1; fi
	@echo "GITHUB_TOKEN present."

check-issue-url: ## Validate ISSUE_URL for agentics
	@if [ -z "$(ISSUE_URL)" ] || ! echo "$(ISSUE_URL)" | grep -q '^https'; then echo "Error: Valid ISSUE_URL (https://...) is required" >&2; exit 1; fi

check-ollama: ## Check Ollama availability
	@code=$$(curl -s -o /dev/null -w '%{http_code}' $(OLLAMA_HOST)/api/tags || echo 000); \
	if [ "$$code" != "200" ]; then echo "Error: Ollama not reachable at $(OLLAMA_HOST)"; exit 1; fi
	@echo "Ollama reachable at $(OLLAMA_HOST)."

check-secrets: ## Scan for leaked secrets
	@echo "Secret scan: ensure .env is gitignored and no tokens committed."
	@git check-ignore .env >/dev/null 2>&1 && echo ".env is ignored." || echo "WARNING: .env not ignored!"

# ---- B9 permission floor (rootless nerdctl bind-mount READ+WRITE) ----
# AGENTS.md (B9) requires the repo to be world-readable and the container write
# targets to be world-writable BEFORE any docker compose run, or rootless nerdctl
# remaps the container uid to the host 'other' class and fails with
# "Permission denied: '/project/src/main.ts'". This target ENFORCES that rule so it
# is never a forgotten manual pre-step.
b9-perms: ## B9: ensure repo is world-readable + write-targets world-writable (rootless nerdctl)
	@echo "B9: applying rootless nerdctl read/write permission floor..."
	@chmod -R a+rX . 2>/dev/null || true
	@for d in src backups openspec results agent-wiki; do \
		if [ -d "$$d" ]; then chmod -R a+rwX "$$d" 2>/dev/null || true; fi; \
	done
	@echo "B9: permission floor applied."

fix-perms: ## Fix file permissions (best-effort)
	@chown -R $(HOST_UID):$(HOST_GID) src agents agent-wiki openspec 2>/dev/null || true
	@echo "Perms fixed (best-effort)."

create-logs: ## Create log directory structure
	@mkdir -p logs/success logs/failed

collect-tests: ## Collect test files (used by CI)
	@echo "Collecting test files..."
	@find agents/agentics/tests -name 'test_*.py' | sort

generate-requirements: ## Regenerate agents/agentics/requirements.txt from docker-files/pip-requirements/requirements.in (via pip-compile container)
	@echo "Compiling requirements.in -> agents/agentics/requirements.txt (pip-compile)"
	$(call docker_run, docker compose -f docker-compose-files/pip.yaml run --rm pip)
	@echo "Regenerated agents/agentics/requirements.txt"

collect-executed: ## Collect executed tests (used by CI)
	@echo "Collecting executed tests..."
	@find agents/agentics/tests -name '*.py' -path '*integration*' -o -name '*.py' -path '*unit*' | sort

stop-containers: ## Stop all project containers
	@if command -v nerdctl >/dev/null 2>&1; then \
		nerdctl ps -q --filter label=com.docker.compose.project 2>/dev/null | xargs -r nerdctl stop 2>/dev/null || true; \
		echo "Stopped compose containers (nerdctl)."; \
	elif command -v docker >/dev/null 2>&1; then \
		docker ps -q --filter label=com.docker.compose.project 2>/dev/null | xargs -r docker stop 2>/dev/null || true; \
		echo "Stopped compose containers (docker)."; \
	else \
		echo "No container runtime found — skipping."; \
	fi

# ---- Cleanup (no Dagger) ----

clean: clean-cache clean-logs stop-containers ## Full clean
	@echo "Cleaning up build artifacts..."
	rm -rf dist release results coverage node_modules || true

clean-cache: ## Remove Python caches only
	find . -name "__pycache__" -type d -exec rm -rf {} + || true
	rm -rf .pytest_cache
	find . -name ".pytest_cache" -type d -exec rm -rf {} + || true

clean-logs: ## Remove all logs
	find . -name "logs" -type d -exec rm -rf {} + 2>/dev/null || true
	find . \( -name "*.logs" -o -name "*.log" \) -delete 2>/dev/null || true

clean-oci: ## Fast OCI nuke (nerdctl prune best practice)
	nerdctl system prune -a -f --volumes || true
	@echo "OCI pruned."
