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

# HERMES_BIN: the project-manager Hermes CLI that record-work.py invokes for prose drafting.
# DEFAULT IS EMPTY on purpose: hermes is a HOST-ONLY CLI (a venv under ~/.hermes with hardcoded
# absolute paths) that CANNOT be bind-mounted read-only into the container without changing the
# source dir's permissions (forbidden). So prose drafting best-effort falls back to a stub inside
# the container (git + openspec metadata is still captured for real). To enable real prose, either
# bake hermes into the agentics image, or pass HERMES_BIN pointing at a world-readable install.
# resolve_hermes() in record-work.py honours $HERMES_BIN -> `hermes` on PATH -> $HOME/.hermes venv.
HERMES_BIN      ?=
# HERMES_MOUNT: intentionally empty. We do NOT mount ~/.hermes (PermissionError under rootless
# nerdctl + must-not-chmod constraint). Left as a hook if an image-baked hermes becomes available.
HERMES_MOUNT    ?=
# RECORD_WORK_CMD: quote-free so it survives the nested sh -c layering inside docker_run
# (the container's /bin/sh is zsh and strips inner quotes). Runs INSIDE unit-test-agents
# (B17, no host python3). We fix the two real in-container gaps so record-work.py can actually
# access the project: (1) add /project/node_modules/.bin to PATH so `openspec` resolves; (2) mark
# /project a safe.directory so git does not exit 128 (dubious ownership under rootless nerdctl uid
# remap). We set a LITERAL absolute PATH (not $PATH-derived) that includes /usr/bin (git lives at
# /usr/bin/git) plus /project/node_modules/.bin (for openspec) — a prior `export PATH=nodebin:$$PATH`
# clobbered git because $$PATH expanded on the host layer without /usr/bin, yielding `git: not found`.
# `hermes` is a host-only CLI not present in the image, so prose drafting best-effort falls
# back to a stub (by design) — the substantive metadata (git + openspec) is still captured.
RECORD_WORK_CMD ?= cd /project && export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/project/node_modules/.bin && git config --global --add safe.directory /project && python3 /project/scripts/record-work.py --change $(CHANGE) $(if $(DATE),--date $(DATE),)
# NOTE: record-work / phase7-archive call $(call docker_run, ...) DIRECTLY (not via a
# run-agentic-cmd target) because a target's $(1) is always empty — the command would be
# lost. This mirrors the working test-check-docs-sync pattern. All execution is INSIDE
# unit-test-agents (rootless nerdctl, /project RW) — NO host python3 (B17). HERMES_* is
# forwarded so record-work.py's prose drafting reaches the project-manager Hermes CLI.
# docker_run: run a `docker compose ... run` command, providing a PTY when needed.
# nerdctl's `compose run` HARDCODES `--interactive --tty`, so the container needs a
# real console; without one it dies with "provided file is not a console". When stdout
# IS a terminal (interactive shell, or the loop runner's `setsid script` wrapper) we run
# the command PLAIN -- this avoids ever NESTING PTYs (which triggers a SIGSTOP deadlock
# under job control). When stdout is NOT a tty (CI / piped / redirected), we wrap in
# `setsid script -qec` to synthesize a console. `setsid` detaches the script session so
# its exit SIGHUP can NOT reach make's later recipe lines (otherwise a plain piped `make`
# silently dies after the first docker_run call with RC=0). Output still flows to stdout.
# `< /dev/null` stops `script` from consuming make's stdin. `script` propagates the
# command's exit code via `_rc` (make exits with it).
#
# NOTE: some `script` variants (util-linux on certain hosts) mis-parse a path token from
# the command string as the typescript output file, causing "script: cannot open /project".
# To stay version-agnostic we write the command to a temp file and pass ONLY
# "/bin/sh <tmpfile>" to `script` (no inline paths), so the typescript file is always the
# explicit trailing `/dev/null`.
define docker_run
	@if [ -t 1 ]; then $(if $(COMPOSE_OVERRIDE),$(COMPOSE_OVERRIDE) )$(1); else _drf=$$(mktemp); _dout=$$(mktemp); cat > "$$_drf" <<'DRF_EOF'
$(if $(COMPOSE_OVERRIDE),$(COMPOSE_OVERRIDE) )$(1)
DRF_EOF
script -qec "/bin/sh $$_drf; echo $$? > $$_drf.rc" /dev/null < /dev/null > "$$_dout" 2>&1; _rc=$$(cat $$_drf.rc 2>/dev/null || echo 0); cat "$$_dout"; rm -f "$$_drf" "$$_drf.rc" "$$_dout"; if [ $$_rc -ne 0 ]; then exit $$_rc; fi; fi
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
        run-agentics phase7-archive b9-perms record-work record-work-prompt squash-commits openspec-new \
        check-deps check-github check-issue-url check-ollama check-secrets \
        fix-perms create-logs \
        collect-tests collect-executed generate-requirements \
        stop-containers \
        clean clean-cache clean-logs clean-oci \
        loop-harness loop-collect loop-ts-floor loop-unit loop-unit-real loop-e2e loop-integration loop-build-app loop-test-app loop-verify loop-tasks \
        wt-create openspec-flow openspec-redeliver \
        squash-commits \
        squash-commits bump-version release-notes tag-release loop-release check-released release bump-local release-prep \
        lint-commits install-git-hooks release-flow loop-final

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
	@$(call docker_run, docker compose -f docker-compose-files/tools.yaml run --rm app npm run build)
	@echo "Build complete"

test-app: b9-perms ## Test the built plugin via docker compose (containers/npm)
	@echo "Running jest via containers/npm..."
	@$(call docker_run, docker compose -f docker-compose-files/tools.yaml run --rm app npm test)
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

changelog: b9-perms ## Generate CHANGELOG.md: render new work as a '## Unreleased' (or versioned) section and OVERWRITE-merge it onto the curated history (idempotent re-run: no duplicate sections). Run 'make bump-from-changelog' to version it.
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e GIT_CONFIG_GLOBAL=/tmp/gitconfig unit-test-agents /project/scripts/gen_changelog.sh) || echo "changelog skipped"
	@$(MAKE) changelog-format

changelog-format: b9-perms ## Normalise CHANGELOG.md with Prettier (markdown-lint clean: tight lists, trimmed whitespace, consistent spacing). Idempotent.
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e GIT_CONFIG_GLOBAL=/tmp/gitconfig unit-test-agents sh -c "cd /project && git config --global --add safe.directory /project && node_modules/.bin/prettier --write CHANGELOG.md") || echo "changelog-format skipped"

bump-from-changelog: b9-perms ## Rename '## Unreleased' -> next version (anchored to released state = tags merged into origin/main, so re-runs do NOT climb), fill gap versions in versions.json with the Obsidian minAppVersion from manifest.json, bump package.json/manifest.json AND the TS test file version literal, re-point v<next> locally. Fail-closed only if already released on the REMOTE.
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e GIT_CONFIG_GLOBAL=/tmp/gitconfig unit-test-agents sh -c "cd /project && git config --global --add safe.directory /project && python3 /project/scripts/bump_from_changelog.py") || echo "bump-from-changelog skipped"
	@$(MAKE) changelog-format

release: clean build-app ## Create release + ZIP check (wires scripts/release.sh which generates release_notes.md + the downloadable zip)
	@if [ -z "$(TAG)" ]; then TAG=$$(node -p "require('./package.json').version"); fi; \
	 echo "=== release: building artifacts via scripts/release.sh (TAG=$$TAG) ==="; \
	 TAG="$$TAG" REPO_NAME="$(REPO_NAME)" DRY_RUN="$(DRY_RUN)" bash scripts/release.sh
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
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e GITHUB_TOKEN=$(GITHUB_TOKEN) -e "TEST_FILTER=$(INTEGRATION_TEST_FILTER)" integration-test-agents)
	@echo "=== Integration test results ==="

test-agents-integration-fast: INTEGRATION_TEST_FILTER = --maxfail=1 -k not slow ## Fast integration tests (fail fast, skip slow)
test-agents-integration-fast: test-agents-integration

test-agents-e2e: INTEGRATION_TEST_FILTER = -m e2e ## End-to-end tests only
test-agents-e2e: test-agents-integration

test-agents: lint-python test-agents-unit-mock test-agents-integration ## All agent tests
test-agents-real: lint-python test-agents-unit test-agents-integration ## Agent tests on REAL logic (no mocks for units; real Ollama/GitHub calls)

test-check-docs-sync: b9-perms ## Hermetic unit tests for scripts/check-docs-sync.py (edge-case fixtures, run INSIDE the unit-test-agents container — no host python3)
	@echo "=== TEST-CHECK-DOCS-SYNC: pytest tests/test_check_docs_sync.py (in container) ==="
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents bash -c "cd /project && python -m pytest tests/test_check_docs_sync.py -q")
	@echo "=== test-check-docs-sync done ==="

check-docs-sync-and-test: check-docs-sync test-check-docs-sync ## Run the doc-sync gate AND its unit tests (proves it behaves, not just passes)

regen-doc-sync-fixtures: b9-perms ## Regenerate the doc-sync .md fixtures from the CURRENT real docs (anchor-checked; run after any AGENTS.md/skill/harness-doc change), then verify
	@echo "=== REGEN-DOC-SYNC-FIXTURES (in container) ==="
	@$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents sh -c "cd /project && python3 /project/scripts/regen_doc_sync_fixtures.py")
	$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents bash -c "cd /project && python -m pytest tests/test_check_docs_sync.py -q")
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
#      EXACT order AGENTS.md prescribes, via `make loop-harness`. NINE loop stages + a FINAL
#      B8 doc-sync gate + a PRE-FLIGHT 0 (check-docs-sync unit tests + live gate) so a broken
#      gate or a drifted doc fails before any heavy stage runs (AGENTS.md Phase 6 + B1/B3/B7.1/B8/B17
#      + ts-test-floor):
#        0. collect guard     (loop-collect)   -- hermetic collection guard (fail fast on dangling imports), audit-mcp-slim-refactor-integrity 4.2
#        0.5 ts-floor         (loop-ts-floor)   -- STRICT TS test/command floor vs origin/main: FAIL if describe/leaf/jest-collected/addCommand drop (silent feature/test removal guard)
#        1. unit tests        (loop-unit)       -- Fast/Unit gate FIRST (hermetic, no Ollama)
#        2. unit-real tests   (loop-unit-real)  -- REAL agent unit tests (live Ollama, no mocks)
#        3. e2e tests         (loop-e2e)        -- the 3 standing e2e gates (ticket20+ticket22+greetings), B1/B3
#        4. integration tests (loop-integration) -- broad agentic integration suite (B17)
#        5. build-app         (loop-build-app)  -- tsc/rollup of the plugin, must exit 0
#        6. test-app          (loop-test-app)  -- jest of the plugin, must pass
#        7. secret-scan-tests  (loop-secret-scan-tests) -- secret-scanner pytest suite, containerized (B9), real gitleaks, fail-closed
#           (the actual gitleaks tree-scan lives in the pre-commit hook + CI, not the loop)
#        8. doc-sync          (check-docs-sync) -- FINAL B8 gate: FAIL if any sync doc drifts (stage order / loop-ts-floor / B-range)
#      B8 durable-behaviour range: B1-B32 (the loop's "laws of physics"; see AGENTS.md). The
#      Canonical stage order (B8 source of truth):
#        loop-collect -> loop-ts-floor -> loop-unit -> loop-unit-real -> loop-e2e -> loop-integration -> loop-build-app -> loop-test-app -> loop-release-tests -> loop-secret-scan-tests -> check-docs-sync
#      Durable behaviours span B1-B32 (the loop's "laws of physics"); this doc-sync gate FAILS if any sync doc drifts on that order / loop-ts-floor / the B1-B32 range.
#      `make check-docs-sync` is the FINAL loop stage (enforced, not advisory) so doc/loop drift
#      fails the whole run (B8 enforced).
#      Each stage fails the whole run if it fails (no silent green). No git commit/push
#      (B4/B14). Optional post-check: `make loop-verify CHANGE=<name>` runs openspec
#      validate + status for the active change.
check-docs-sync: b9-perms ## B8 doc/loop sync gate (FINAL loop stage) — FAIL if any B8 source-of-truth doc drifts (stage order / loop-ts-floor / B-range B1-B32). Runs INSIDE unit-test-agents (no host python3).
	@echo "=== B8 DOC-SYNC: verify loop/loop-harness docs agree (stage order, loop-ts-floor, B-range) — in container ==="
	@$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents sh -c "cd /project && python3 /project/scripts/check-docs-sync.py")

loop-collect: ## Loop gate 0: hermetic collection guard (fail fast on dangling imports)
	@echo "=== LOOP-HARNESS [collect] collection guard (no dangling imports) ==="
	@$(MAKE) test-agents-collect

loop-ts-floor: ## Loop gate 0.5: STRICT TS test/command floor — FAIL if current describe/leaf/jest-collected/addCommand counts drop below origin/main (silent feature/test removal guard)
	@echo "=== LOOP-HARNESS [ts-floor] strict TS test/command surface floor vs origin/main ==="
	@bash scripts/ts_test_floor.sh

loop-unit: ## Loop gate 1: hermetic unit tests (fast, no Ollama/GitHub)
	@echo "=== LOOP-HARNESS [1/6] unit tests (mocked, hermetic) ==="
	@$(MAKE) test-agents-unit-mock

loop-unit-real: ## Loop gate 2: REAL agent unit tests (live Ollama, no mocks)
	@echo "=== LOOP-HARNESS [2/6] real agent unit tests (Ollama) ==="
	@$(MAKE) test-agents-unit

loop-e2e: ## Loop gate 3: standing e2e gates (ticket20 + ticket22 + greetings)
	@echo "=== LOOP-HARNESS [3/6] e2e gates (-m e2e) ==="
	@$(MAKE) test-agents-e2e

loop-integration: ## Loop gate 4: broad agentic integration suite (B17) — excludes e2e (its own stage) and slow full-pipeline tests
	@echo "=== LOOP-HARNESS [4/6] integration suite (-m 'integration and not e2e and not slow') ==="
	@$(MAKE) test-agents-integration INTEGRATION_TEST_FILTER="-m 'integration and not e2e and not slow'"

loop-build-app: ## Loop gate 5: build the Obsidian plugin (tsc/rollup, exit 0)
	@echo "=== LOOP-HARNESS [5/6] build-app ==="
	@$(MAKE) build-app

loop-test-app: ## Loop gate 6: run jest on the plugin
	@echo "=== LOOP-HARNESS [6/6] test-app ==="
	@$(MAKE) test-app

loop-release-tests: b9-perms ## Loop gate 6.5: release-pipeline + README-sync dry-run tests (root tests/test_*.py). Proves the GitHub release body + zip are built correctly AND the README stays in sync with package.json/CHANGELOG/commands — WITHOUT calling GitHub. Runs INSIDE unit-test-agents.
	@echo "=== LOOP-HARNESS [6.5] release-pipeline + README-sync dry-run tests ==="
	@$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e DRY_RUN=1 -e GIT_CONFIG_GLOBAL=/tmp/gitconfig unit-test-agents sh -c "cd /project && DRY_RUN=1 python -m pytest tests/test_release_pipeline_dryrun.py tests/test_readme_sync.py tests/test_release_notes_bump.py -v")

loop-harness: ## Full loop-harness: SINGLE source of truth = scripts/run-loop-harness.sh.
	@# This target delegates to the script so the per-stage timeouts + docker-kill
	@# logic are ALWAYS applied (never a bare `make` chain that can hang forever).
	@# The script calls back into these same `loop-*` targets, so what runs is
	@# identical whether you invoke `make loop-harness` or the script directly.
	@bash scripts/run-loop-harness.sh
	@echo "=== LOOP-HARNESS COMPLETE: all gates green in order (collect -> ts-floor -> unit -> unit-real -> e2e -> integration -> build-app -> test-app -> release-tests -> secret-scan-tests -> check-docs-sync) ==="

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
phase7-archive: ## Archive an OpenSpec change (spec only) + auto-emit work-log (both containerised, no host python3 — B17) + assert durable E2E present
	@test -n "$(CHANGE)" || { echo "ERROR: set CHANGE=<openspec-change-name>"; exit 1; }
	@# Phase-7 work-log (record-work) runs FIRST so it references the LIVE change dir,
	@# before `openspec archive` moves it. Three-step hermes handoff:
	@# container --emit-prompt -> host hermes -z -> container --prose-file (no host python3, no
	@# chmod on ~/.hermes, B17). Falls back to stub if host hermes is unavailable.
	@$(eval H := /project/backups/record-work-$(CHANGE))
	@echo "Phase-7 work-log (step 1/3 — container): gathering context + emitting prompt..."
	@$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e GIT_CONFIG_GLOBAL=/tmp/gitconfig -e HERMES_PROFILE=project-manager unit-test-agents sh -c "$(RECORD_WORK_CMD) --emit-prompt $(H).prompt")
	@echo "Phase-7 work-log (step 2/3 — HOST): hermes -z draft..."
	@if command -v hermes >/dev/null 2>&1; then \
	  hermes profile use project-manager 2>/dev/null; \
	  { hermes -z "$$(cat backups/record-work-$(CHANGE).prompt)" > backups/record-work-$(CHANGE).prose 2>/dev/null; } || true; \
	fi
	@echo "Phase-7 work-log (step 3/3 — container): writing entry with prose..."
	@$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e GIT_CONFIG_GLOBAL=/tmp/gitconfig -e HERMES_PROFILE=project-manager unit-test-agents sh -c "$(RECORD_WORK_CMD) --prose-file $(H).prose") || echo "WARN: record-work failed for $(CHANGE) (see above); archive still proceeds."
	@rm -f backups/record-work-$(CHANGE).prompt backups/record-work-$(CHANGE).prose 2>/dev/null || true
	@# B16 (enforce-task-completion-gate): FAILS-CLOSED. Refuse to archive a change
	@#      with open `- [ ]` tasks. Runs INSIDE the container (no host python3, B17).
	@echo "B16: checking for open tasks in $(CHANGE) (in container)..."
	@$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e GIT_CONFIG_GLOBAL=/tmp/gitconfig unit-test-agents sh -c "python3 /project/scripts/assert_no_open_tasks_cli.py $(CHANGE)") || { echo "FAIL(B16): $(CHANGE) has open tasks (see above). Tick them in tasks.md, then re-run."; exit 1; }
	@# B1: the persistent E2E harness must still exist -- never deleted on archive.
	@test -f agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py || { echo "FAIL(B1): persistent e2e harness missing -- do NOT remove it on archive."; exit 1; }
	@# B4: refuse to touch git. This target archives ONLY the openspec spec; it does
	@#      NOT commit or push. (User commits the generated TS/tests separately & deliberately.)
	@echo "Archiving spec for $(CHANGE) (openspec archive -y -- spec only, no git commit/push)..."
	@openspec archive -y $(CHANGE)
	@echo "DONE: spec archived. No git commit/push performed. Verify + commit TS/tests manually if intended."

# ---- loop-finish: green-gated release finalisation (B23, loop-green-auto-squash-changelog) ----
# When the loop gate is GREEN (B20 pre-flight) and the backlog is clear (every active change
# has open=0), finalise the release LOCALLY and safely:
#   assert-backlog-clear -> archive-all-complete -> squash-commits -> changelog
#   -> bump-from-changelog -> changelog-format.  NO push (B4/B14).
assert-backlog-clear: ## FAILS CLOSED if any active OpenSpec change still has an open `- [ ]` task.
	@echo "=== ASSERT-BACKLOG-CLEAR: every active change must have open=0 ==="
	@bad=0; for d in $$(ls -1 openspec/changes 2>/dev/null); do \
		if [ "$$d" = "archive" ] || [ "$$d" = ".gitkeep" ]; then continue; fi; \
		tf=openspec/changes/$$d/tasks.md; \
		if [ ! -f "$$tf" ]; then continue; fi; \
		open=$$(grep -cE '^- \[ \]' $$tf); \
		if [ "$$open" != "0" ]; then echo "  BACKLOG NOT CLEAR: $$d has $$open open task(s)"; bad=1; fi; \
	done; \
	if [ "$$bad" = "1" ]; then echo "ASSERT-BACKLOG-CLEAR: FAILED -- clear the backlog (tick + archive all changes) before loop-finish."; exit 1; fi; \
	echo "OK: no active change has open tasks."

archive-all-complete: assert-backlog-clear ## Archive EVERY active OpenSpec change (B16 gate per change).
	@echo "=== ARCHIVE-ALL-COMPLETE: archiving all active changes (open=0 enforced) ==="
	@for d in $$(ls -1 openspec/changes 2>/dev/null); do \
		if [ "$$d" = "archive" ] || [ "$$d" = ".gitkeep" ]; then continue; fi; \
		tf=openspec/changes/$$d/tasks.md; \
		if [ ! -f "$$tf" ]; then continue; fi; \
		echo "  archiving $$d ..."; \
		$(MAKE) phase7-archive CHANGE=$$d || { echo "ARCHIVE-ALL: FAILED on $$d (see above)."; exit 1; }; \
	done; \
	echo "=== ARCHIVE-ALL-COMPLETE DONE: all active changes archived (specs merged). ==="

loop-finish: archive-all-complete ## Green-gated release finalisation: archive-all -> squash -> changelog -> bump-from-changelog -> format. NO push (B4/B14). Run ONLY after `make loop-harness` is GREEN (B20).
	@echo "=== LOOP-FINISH: backlog clear + all changes archived; finalising release LOCALLY ==="
	@$(MAKE) squash-commits
	@$(MAKE) changelog
	@$(MAKE) bump-from-changelog
	@$(MAKE) changelog-format
	@echo "=== LOOP-FINISH COMPLETE: squashed typed commit + regenerated CHANGELOG (## Unreleased -> ## <next>) + bumped package/manifest/versions.json. NO push (B14) -- push deliberately. ==="

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

wt-create: ## Create an isolated git worktree for an OpenSpec change: git worktree add worktrees/<name> -b feat/<name> (REPO_ROOT/node_modules symlinked in). Never touches the parent working tree.
	@test -n "$(NAME)" || { echo "ERROR: NAME=<change> required. Run: make wt-create NAME=<kebab-name>"; exit 1; }
	@REPO_ROOT=$$(git rev-parse --show-toplevel); WT=$$REPO_ROOT/worktrees/$(NAME); \
	if [ -d "$$WT" ]; then echo "WT-CREATE: $$WT already exists — reuse it."; \
	else git worktree add "$$WT" -b wt/$(NAME) && echo "WT-CREATE: created $$WT on local sandbox branch wt/$(NAME)"; fi; \
	if [ ! -e "$$WT/node_modules" ] && [ -d "$$REPO_ROOT/node_modules" ]; then ln -s ../../node_modules "$$WT/node_modules" && echo "WT-CREATE: symlinked node_modules into worktree (gitignored — stays in worktree only)."; fi; \
	echo "WT-CREATE: done. Run flow: make openspec-flow NAME=$(NAME)"

# ---- OpenSpec change → worktree → loop → archive → finalize → deliver-as-PR (B24 + B12 override) ----
# ALL work happens INSIDE the worktree; the parent working tree is never touched. Delivery is a
# `git push feat/<name>` (PR), NOT a file copy into the parent (that copy would re-introduce pollution).
# Squashing is performed only INSIDE the worktree (agent/harness behaviour; the squash-commits script
# itself is unrestricted). Parallel-safe: unique compose project name otu-<name> per flow.
openspec-flow: ## Agent-driven change lifecycle CONFINED to a worktree: create worktree -> scaffold -> generate -> loop gate -> archive -> finalize (squash in worktree) -> (--push) PR. Args: NAME=<change> [PUSH=1] [NO_AGENTICS=1] [NO_LOOP=1]
	@test -n "$(NAME)" || { echo "ERROR: NAME=<change> required. Run: make openspec-flow NAME=<kebab-name> [PUSH=1]"; exit 1; }
	@bash scripts/openspec-change-flow.sh --name $(NAME) $(if $(PUSH),--push,) $(if $(NO_AGENTICS),--no-agentics,) $(if $(NO_LOOP),--no-loop,)

openspec-redeliver: ## Re-enter the worktree, regenerate/re-squash, and FORCE-PUSH to the SAME PR branch (feat/<name>) after corrections. Guarded against main/protected refs. Args: NAME=<change> [PUSH_REMOTE=origin]
	@test -n "$(NAME)" || { echo "ERROR: NAME=<change> required. Run: make openspec-redeliver NAME=<kebab-name>"; exit 1; }
	@REPO_ROOT=$$(git rev-parse --show-toplevel); WT=$$REPO_ROOT/worktrees/$(NAME); BRANCH=feat/$(NAME); \
	test -d "$$WT" || { echo "REDELIVER: worktree $$WT not found — run 'make openspec-flow NAME=$(NAME)' first."; exit 1; }; \
	if [ "$(NAME)" = "main" ] || [ "$$BRANCH" = "main" ]; then echo "REDELIVER: REFUSING to force-push main."; exit 1; fi; \
	cd "$$WT"; \
	echo "=== REDELIVER: regenerating inside worktree $$WT ==="; \
	$(MAKE) run-agentics CHANGE=$(NAME) || true; \
	$(MAKE) squash-commits; \
	$(MAKE) changelog; $(MAKE) bump-from-changelog; $(MAKE) changelog-format; \
	echo "=== REDELIVER: force-pushing $$BRANCH to $(PUSH_REMOTE) (--force-with-lease; same PR branch) ==="; \
	git push --force-with-lease $(PUSH_REMOTE) $$BRANCH; \
	echo "REDELIVER: PR branch updated in place. Parent working tree untouched."

# ---- PR-review stability (B28): gh-driven comment resolution, no squash ----
# B28b: when asked to "go to the PR for <branch>" / "resolve the PR comments", fetch the PR's
# comments + review threads via gh and resolve them. This target ONLY fetches + prints (no
# commit/push) — the agent reads the threads, fixes the code, commits as NORMAL (non-squashed)
# Conventional commits, and pushes normally. B28a forbids squash/force on an engaged PR, so
# pr-resolve + squash-commits are mutually exclusive on a reviewed branch.
pr-resolve: ## B28b: fetch + print PR comments/review threads for BRANCH via gh (no commit/push). Usage: make pr-resolve BRANCH=<branch>
	@test -n "$(BRANCH)" || { echo "ERROR: BRANCH=<branch> required. Run: make pr-resolve BRANCH=<branch>"; exit 1; }
	@bash scripts/pr_resolve.sh $(BRANCH)

# ---- PR-review stability (B29): two-way interaction — comment the fix + commit on green gate ----
# B29a: post a PR comment (the agent signals a fix to the participant). B29b: resolve-and-comment =
# fetch threads -> agent fixes -> run loop-harness (B20 pre-flight) -> on GREEN commit NORMALLY,
# post fix comments, push normally (no force/squash). B29c: the agent never self-resolves/approves.
pr-comment: ## B29a: post BODY as a comment on the open PR for BRANCH via gh (no commit/push). Usage: make pr-comment BRANCH=<branch> BODY="<text>"
	@test -n "$(BRANCH)" || { echo "ERROR: BRANCH=<branch> required."; exit 1; }
	@test -n "$(BODY)" || { echo "ERROR: BODY=\"<text>\" required."; exit 1; }
	@bash scripts/pr_comment.sh $(BRANCH) "$(BODY)"

pr-resolve-and-comment: ## B29b: fetch PR threads (pr_resolve.sh); agent fixes; run loop-harness; on GREEN commit normally, post fix comments, push normally (no squash/force). Usage: make pr-resolve-and-comment BRANCH=<branch>
	@test -n "$(BRANCH)" || { echo "ERROR: BRANCH=<branch> required."; exit 1; }
	@bash scripts/pr_resolve.sh $(BRANCH)
	@echo "=== B29b: apply fixes for the threads above, then 'make loop-harness'. On GREEN: ==="
	@echo "  1) git commit -m '<type>(<scope>): <fix> (resolves PR comment)'  (NORMAL, non-squashed)"
	@echo "  2) make pr-comment BRANCH=$(BRANCH) BODY=\"Fixed in <sha>: <summary> — resolves <comment>\""
	@echo "  3) git push origin $(BRANCH)  (normal push, NO --force, NO squash — B28a)"
	@echo "If 'make loop-harness' is RED, do NOT commit/push; report the failing stage (B20)."

record-work-prompt: b9-perms ## Steps 1+2 of the hermes handoff: container emit-prompt + host hermes -z (used by record-work)
	@$(eval H := /project/backups/record-work-$(CHANGE))
	@echo "(step 1/3 — container): gathering context + emitting prompt..."
	@$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e GIT_CONFIG_GLOBAL=/tmp/gitconfig -e HERMES_PROFILE=project-manager unit-test-agents sh -c "$(RECORD_WORK_CMD) --emit-prompt $(H).prompt")
	@echo "(step 2/3 — HOST): hermes -z drafting..."
	@if command -v hermes >/dev/null 2>&1; then hermes profile use project-manager 2>/dev/null; fi
	@if command -v hermes >/dev/null 2>&1; then hermes -z "$$(cat backups/record-work-$(CHANGE).prompt)" > backups/record-work-$(CHANGE).prose 2>/dev/null || true; fi

record-work: b9-perms ## Phase 7 work-log: write agent-wiki/YYYY-MM-DD-<change>.md via hermes handoff (container prompts, host drafts, container writes — no host python3, no chmod on ~/.hermes)
	@test -n "$(CHANGE)" || { echo "ERROR: set CHANGE=<openspec-change-name> (e.g. make record-work CHANGE=uuid-modal-agentic-generation)"; exit 1; }
	@$(eval H := /project/backups/record-work-$(CHANGE))
	@$(eval L := backups/record-work-$(CHANGE))
	@echo "=== RECORD-WORK: agent-wiki entry for $(CHANGE) ==="
	@if [ ! -f $(L).prose ]; then echo "(prompt/prose absent — running steps 1+2 via record-work-prompt)"; $(MAKE) --quiet record-work-prompt CHANGE=$(CHANGE); fi
	@if [ ! -f $(L).prose ]; then echo "WARN: no prose handoff — will use stub body"; fi
	@echo "(step 3/3 — container): writing entry with prose..."
	@$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm -e GIT_CONFIG_GLOBAL=/tmp/gitconfig -e HERMES_PROFILE=project-manager unit-test-agents sh -c "$(RECORD_WORK_CMD) --prose-file $(H).prose")
	@rm -f $(L).prompt $(L).prose 2>/dev/null || true
	@echo "=== RECORD-WORK complete: review agent-wiki/$$(date +%Y-%m-%d)-$(CHANGE).md ==="

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

squash-commits: ## Squash ALL commits ahead of `main` into ONE thoroughly-typed Conventional commit (Hermes, project-manager). The FIRST line MUST be `type(scope): subject` (type in feat|fix|docs|refactor|perf|test|chore|build|ci|style|revert) so the changelog sections and the version bump are tagged accordingly. The drafted message is FAIL-CLOSED through `commitlint` before commit. NO push (B14).
	@# B30 (no-revert / squash-pre-PR-only) + B28a (no squash on engaged PR):
	@# Squash is ONLY allowed while the branch is a LOCAL pre-PR change (not yet an open PR).
	@# Once the branch is an open PR for ANY reason (engagement or not), or already tracks a
	@# pushed remote state, squash is FORBIDDEN (it would rewrite public history). Reverting
	@# commits is NEVER allowed (B30a) — corrections are forward NORMAL commits only.
	@# Fail CLOSED when gh confirms an open PR / pushed branch; fail OPEN (skip guard) when
	@# gh/token is unavailable so a genuine local pre-PR squash is never silently blocked.
	@# B30d (explicit override): ALLOW_SQUASH=1 lets the user deliberately bypass the guard
	@# (e.g. a local pre-merge cleanup the reviewer agreed to). OFF by default; ALWAYS prints a
	@# loud warning so the rewrite is never silent. Does NOT bypass B30a (no revert).
	@if [ "$$(echo $${ALLOW_SQUASH:-0})" = "1" ]; then \
		echo "B30d: ALLOW_SQUASH=1 set -- OVERRIDING the pre-PR squash guard on purpose."; \
		echo "B30d: WARNING: this rewrites history on branch $$BRANCH. You asked for it explicitly."; \
	else \
	BRANCH=$$(git rev-parse --abbrev-ref HEAD 2>/dev/null); \
	if command -v gh >/dev/null 2>&1 && [ -n "$$GH_TOKEN" ]; then \
		PRJSON=$$(gh pr view "$$BRANCH" --json number,comments,reviews 2>/dev/null); \
		if [ -n "$$PRJSON" ]; then \
			echo "B30: branch $$BRANCH is the head of an open PR -- SQUASH FORBIDDEN (pre-PR only)."; \
			echo "B30: commit corrections as NORMAL (non-squashed) Conventional commits and push normally. Aborting (no commit/reset/push)."; \
			echo "B30d: to override deliberately, re-run with ALLOW_SQUASH=1 (rewrites history -- you asked)."; \
			exit 1; \
		fi; \
		echo "B30: $$BRANCH is not the head of an open PR -- squash allowed (pre-PR)."; \
	elif [ -n "$$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)" ]; then \
		echo "B30: branch $$BRANCH already tracks a pushed remote ($$(git rev-parse --abbrev-ref --symbolic-full-name @{u})) -- SQUASH FORBIDDEN (pre-PR only)."; \
		echo "B30: commit corrections as NORMAL (non-squashed) Conventional commits and push normally. Aborting (no commit/reset/push)."; \
		echo "B30d: to override deliberately, re-run with ALLOW_SQUASH=1 (rewrites history -- you asked)."; \
		exit 1; \
	else \
		echo "B30: gh/token unavailable and no upstream -- skipping PR-state guard (fail-open, pre-PR squash allowed)."; \
	fi; \
	fi
	@# Diff base is `main` (the real branch origin), NOT the loose upstream.
	@# Hermes receives the changed-file list + diff-stat vs `main` and must
	@# write a THOROUGH body describing what the substantive files
	@# ACTUALLY do (behaviour), not meta commentary about the commit tool.
	@# CRITICAL (release-automation): the FIRST line is the Conventional-Commits
	@# tag (e.g. `feat(loop): ...`, `fix(agentics): ...`, `docs(readme): ...`).
	@# The changelog sections (chglog/config.yml) and `bump-version` PART are
	@# derived from this type, so it MUST start with `^(feat|fix|docs|refactor
	@# |perf|test|chore|build|ci|style|revert)(\\\(.*\\))?:\\s`. Fail-closed otherwise.
	@# HARDENING (enhance-squash-commits): after Hermes drafts the message we run
	@# `commitlint` on it (the same gate as the per-commit `commit-msg` hook).
	@# If commitlint rejects it, we restore the pre-squash state and abort -- no
	@# untyped/malformed commit is ever created. This is the "tag it accordingly"
	@# guarantee that drives the CHANGELOG sections and the version bump.
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
	PROMPT="You are writing ONE git commit message in Conventional Commits / Angular style for a branch being squashed into a single commit. RULE 1 (mandatory): the FIRST line is EXACTLY 'type(scope): subject' where type is ONE of: feat, fix, docs, refactor, perf, test, chore, build, ci, style, revert; scope is the area (e.g. loop, agentics, readme, release); subject is imperative, <=72 chars, no trailing period. RULE 2: then a blank line, then a THOROUGH human-readable body (wrapped ~72 cols) describing WHAT the changed code now does and WHY, grounded in the actual files below -- not meta commentary about the commit command. Cover substantive areas: the OpenSpec loop-harness engineering (deterministic code_integrator floor, B1-B31 durable behaviours), agentic pipeline changes, Makefile / docker-compose / Containerfile changes, OpenSpec specs merged, and any test/behaviour fixes. Be specific. Output ONLY the raw commit message (title + blank + body), no code fences, no preamble. CHANGED FILES vs main:$$(printf '\n%s' $$FILES) DIFF STAT vs main:$$(printf '\n%s' $$STAT)"; \
	MSG=$$(hermes -z "$$PROMPT" 2>/dev/null); \
	if [ -z "$$MSG" ]; then echo "COMMIT: Hermes returned no message -- aborting (no empty commit)."; git reset --quit $$MAIN >/dev/null 2>&1 || true; exit 1; fi; \
	FIRST=$$(printf '%s' "$$MSG" | head -1); \
	if ! printf '%s' "$$FIRST" | grep -qE '^(feat|fix|docs|refactor|perf|test|chore|build|ci|style|revert)(\([^)]*\))?:[[:space:]]'; then \
		echo "COMMIT: FAIL-CLOSED -- first line is not a typed Conventional commit: '$$FIRST'"; \
		echo "COMMIT: refusing to create an untyped commit (changelog + bump need the type)."; \
		git reset --quit $$MAIN >/dev/null 2>&1 || true; exit 1; \
	fi; \
	if ! printf '%s\n' "$$MSG" | "$(CURDIR)/node_modules/.bin/commitlint" --config "$(CURDIR)/commitlint.config.cjs"; then \
		echo "COMMIT: FAIL-CLOSED -- message failed commitlint (Conventional-Commits gate)."; \
		echo "COMMIT: refusing to create a non-conformant commit (changelog + bump need a valid type)."; \
		git reset --quit $$MAIN >/dev/null 2>&1 || true; exit 1; \
	fi; \
	git commit -m "$$MSG" && echo "COMMIT: created one TYPED Conventional commit (commitlint-passed, not pushed -- B14). Review with 'git show'."

# ---- loop-final: review-approved squash + changelog + force-push (B32) ----
#
# B32 (loop-final-reviewed-squash): the ONLY sanctioned path that squashes + force-pushes an
# already-open PR. It is gated on an EXPLICIT human approval and a FRESH green loop-harness:
#   1. APPROVED=1 MUST be set (the agent sets it ONLY after a human approval phrase such as
#      "PR looks great" / "looks good" / "approved to finalize"). Without it -> fail closed.
#   2. BRANCH=<feat/...> MUST be given and MUST NOT be main/origin/main.
#   3. A FRESH `make loop-harness` runs FIRST and MUST be green -- history is NEVER rewritten
#      on a red gate.
#   4. On green: squash-commits (via the B30d ALLOW_SQUASH=1 sanctioned override) -> changelog
#      -> bump-from-changelog -> changelog-format.
#   5. `git push --force-with-lease` the feature branch ONLY. B30a stays absolute (no git revert).
loop-final: ## B32: review-approved finalisation of an OPEN PR: fresh loop-harness (green) -> squash -> changelog -> force-with-lease push the feature branch. Requires APPROVED=1 + BRANCH=<feat/...>. Refuses main.
	@test "$$(echo $${APPROVED:-0})" = "1" || { echo "LOOP-FINAL: FAIL-CLOSED -- APPROVED=1 required (set ONLY after an explicit human PR approval). Aborting: no squash, no force-push."; exit 1; }
	@test -n "$(BRANCH)" || { echo "LOOP-FINAL: ERROR -- BRANCH=<feat/...> required."; exit 1; }
	@if [ "$(BRANCH)" = "main" ] || [ "$(BRANCH)" = "origin/main" ]; then echo "LOOP-FINAL: REFUSING to finalise/force-push main."; exit 1; fi
	@CUR=$$(git rev-parse --abbrev-ref HEAD 2>/dev/null); \
	if [ "$$CUR" != "$(BRANCH)" ]; then echo "LOOP-FINAL: ERROR -- checked-out branch '$$CUR' != BRANCH '$(BRANCH)'. Checkout the feature branch first."; exit 1; fi
	@echo "=== LOOP-FINAL (B32): human-approved. Running FRESH loop-harness before any history rewrite ==="
	@$(MAKE) loop-harness || { echo "LOOP-FINAL: loop-harness RED -- aborting. No squash, no force-push (B30c: forward fix a red gate, never rewrite)."; exit 1; }
	@echo "=== LOOP-FINAL: loop-harness GREEN -- squashing (B30d sanctioned override) + regenerating changelog ==="
	@$(MAKE) squash-commits ALLOW_SQUASH=1
	@$(MAKE) changelog
	@$(MAKE) bump-from-changelog
	@$(MAKE) changelog-format
	@echo "=== LOOP-FINAL: force-pushing $(BRANCH) with --force-with-lease (feature branch only; never main) ==="
	@git push --force-with-lease origin $(BRANCH)
	@echo "=== LOOP-FINAL COMPLETE (B32): squashed typed commit + regenerated CHANGELOG + force-with-lease push to $(BRANCH). B30a still absolute (no revert). ==="

# ---- Commit linting gate (enhance-squash-commits) ----
#
# `lint-commits` runs commitlint (using the repo's commitlint.config.cjs) over the
# commits being squashed (or HEAD when run standalone). It is the "changelog lint"
# the user asked for: every squashed/committed message MUST be a valid Conventional
# Commit so the type drives the CHANGELOG sections and the bump PART.
# `install-git-hooks` wires the per-commit `commit-msg` hook so typos are caught at
# commit time. Both are hermetic (commitlint is a committed devDependency).
COMMITLINT_BIN := $(CURDIR)/node_modules/.bin/commitlint
COMMITLINT_CFG := $(CURDIR)/commitlint.config.cjs

lint-commits: ## Lint the commits being squashed (or HEAD) with commitlint (Conventional-Commits gate). Fail-closed: non-zero exit on any invalid message.
	@test -x "$(COMMITLINT_BIN)" || { echo "LINT: commitlint not found at $(COMMITLINT_BIN) -- run 'npm install' first."; exit 1; }
	@MAIN=$$(git rev-parse --verify origin/main 2>/dev/null || git rev-parse --verify main 2>/dev/null || echo ""); \
	if [ -z "$$MAIN" ]; then echo "LINT: no 'main' ref -- linting HEAD only."; "$(COMMITLINT_BIN)" --config "$(COMMITLINT_CFG)" --from HEAD~1 --to HEAD || exit 1; \
	else echo "LINT: linting $$MAIN..HEAD with commitlint..."; "$(COMMITLINT_BIN)" --config "$(COMMITLINT_CFG)" --from $$MAIN --to HEAD || exit 1; fi; \
	echo "LINT: all commits in range are valid Conventional Commits."

install-git-hooks: ## Wire the per-commit `commit-msg` + `pre-commit` hooks into .git/hooks.
	@test -f git-hooks/commit-msg || { echo "HOOKS: git-hooks/commit-msg missing -- aborting."; exit 1; }
	@chmod +x git-hooks/commit-msg
	@mkdir -p .git/hooks
	@cp -f git-hooks/commit-msg .git/hooks/commit-msg && chmod +x .git/hooks/commit-msg
	@test -f git-hooks/pre-commit || { echo "HOOKS: git-hooks/pre-commit missing -- skipping pre-commit install."; } || true
	@if [ -f git-hooks/pre-commit ]; then \
		chmod +x git-hooks/pre-commit; \
		cp -f git-hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit; \
		echo "HOOKS: installed .git/hooks/pre-commit (trailing-whitespace auto-fix)."; \
	fi
	@echo "HOOKS: installed .git/hooks/commit-msg (per-commit Conventional-Commit lint)."

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
	@$(call docker_run, docker compose -f docker-compose-files/agents.yaml run --rm unit-test-agents sh -c "cd /project && python3 /project/scripts/update-release-notes.py README.md")

tag-release: ## Create a LOCAL git tag v<version> (NO push -- B14). Run AFTER squash-commits.
	@command -v node >/dev/null 2>&1 || { echo "TAG: node required -- aborting."; exit 1; }
	@VER=$$(node -p "require('./package.json').version"); \
	TAG="v$$VER"; \
	if git rev-parse "$$TAG" >/dev/null 2>&1; then echo "TAG: $$TAG already exists -- skipping."; exit 0; fi; \
	git tag -a "$$TAG" -m "Release $$VER"; \
	echo "TAG: created local tag $$TAG (NOT pushed -- B14). Push deliberately with 'git push origin $$TAG'."; \
	echo "TAG: verify with 'git show $$TAG'."

release-prep: check-released ## LOCAL release prep (publish happens in CI): bump (Obsidian way) -> typed squash -> sectioned changelog -> README release-notes -> local tag. Refuses if current version already released on GitHub. NO push (B14) -- the actual GitHub release is done by .github/workflows/release.yml on merge to main.
	@set -e; \
	echo "=== RELEASE-PREP: local release prep (guarded) ==="; \
	$(MAKE) bump-version PART=$(PART); \
	$(MAKE) squash-commits; \
	$(MAKE) changelog; \
	$(MAKE) release-notes; \
	$(MAKE) tag-release; \
	echo "=== RELEASE-PREP COMPLETE: bump + squashed typed commit + changelog + release-notes + local tag. The GITHUB RELEASE is cut by CI (.github/workflows/release.yml) when you merge to main / push the tag. NO push here (B14). ==="

loop-release: ## Post-green release stage: guard (generated TS changed + not already released) -> bump -> squash -> changelog -> release-notes -> local tag. NO push.
	@set -e; \
	echo "=== LOOP-RELEASE: post-green release stage ==="; \
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
	@set -e; \
	echo "=== BUMP-LOCAL: bump version + local tag only (no squash/changelog/publish) ==="; \
	$(MAKE) bump-version PART=$(PART); \
	$(MAKE) tag-release; \
	echo "=== BUMP-LOCAL COMPLETE: version bumped (Obsidian way) + local tag. NO commit squash, NO changelog, NO push (B14). ==="

# ---- Canonical release-flow (enhance-squash-commits) ----
#
# Single command encoding the user's exact flow, LOCAL only (no push, B14):
#   1. squash-commits  -- one TYPED Conventional commit (commitlint-gated: "tag it accordingly")
#   2. bump-local      -- check-released guard -> bump-version (Obsidian way, refuses unless NEW
#                         plugin TS in src/main.ts vs origin/main) -> tag-release (LOCAL v<version>)
#   3. changelog       -- regenerate CHANGELOG.md so the new ## <version> section is present
#                         (driven by the local v<version> tag)
#   4. release-notes   -- refresh the README release-notes block to the new version
# The bump is guarded so it only advances to the NEXT UNRELEASED version (no semver gap vs the
# latest released, and not already released on GitHub -- tolerant of X / vX). The tag is local
# only; pushing commit + tag remains a deliberate human action.
release-flow: ## Canonical local release flow: squash (typed, commitlint-gated) -> bump to next unreleased version (TS+released guarded) -> changelog -> release-notes. NO push (B14).
	@set -e; \
	echo "=== RELEASE-FLOW: squash -> bump-local -> changelog -> release-notes (LOCAL, no push) ==="; \
	$(MAKE) squash-commits; \
	$(MAKE) bump-local PART=$(PART); \
	$(MAKE) changelog; \
	$(MAKE) release-notes; \
	echo "=== RELEASE-FLOW COMPLETE: one typed squashed commit + bumped version (Obsidian way) + local tag + refreshed CHANGELOG.md (new ## <version>) + README release-notes. NO push (B14). ==="

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

check-secrets: loop-secret-scan  ## [ALIAS] Deprecated name -> loop-secret-scan (containerized gitleaks loop gate).
	@true

# AGENTS.md (B9) requires the repo to be world-readable and the container write
# remaps the container uid to the host 'other' class and fails with
# "Permission denied: '/project/src/main.ts'". This target ENFORCES that rule so it
# is never a forgotten manual pre-step.
b9-perms: ## B9: ensure repo is world-readable + write-targets world-writable (rootless nerdctl)
	@echo "B9: applying rootless nerdctl read/write permission floor..."
	@chmod -R a+rX . 2>/dev/null || true
	@for d in src backups openspec results agent-wiki tests; do \
		if [ -d "$$d" ]; then chmod -R a+rwX "$$d" 2>/dev/null || true; fi; \
	done
	@# Release/changelog write-targets (rootless nerdctl remaps container uid to host 'other')
	@for f in CHANGELOG.md package.json manifest.json versions.json README.md src/__tests__/main.test.ts src/main.ts; do \
		if [ -f "$$f" ]; then chmod a+rw "$$f" 2>/dev/null || true; fi; \
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

# ---- Secret scanning (gitleaks) — HOOK/CI SCAN + LOOP TESTS, CONTAINER-ONLY (B9) ----
#
# The actual gitleaks TREE SCAN is NOT a loop-harness stage: it lives in the
# pre-commit hook (`scripts/secret_scanner.py --staged`), the commit-msg hook
# (`--message-file`), and CI (.github/workflows/trufflehog.yml). A standalone
# `loop-secret-scan` target exists for on-demand scans only.
# The loop stage is `loop-secret-scan-tests` — it runs the scanner's OWN pytest
# suite INSIDE the `gitleaks-tests` compose container
# (docker-compose-files/gitleaks-tests.yaml), exercising the REAL gitleaks binary.
# The Makefile NEVER shells out to `python3 scripts/secret_scanner.py` or a bare
# host `gitleaks` binary for the scan — docker compose only (B9). The Python
# wrapper remains the LOCAL fail-closed hook guard (git-hooks/), not a Makefile command.
# There is exactly ONE canonical loop scan entry: loop-secret-scan-tests.
#
# Images:
#   containers/gitleaks/Dockerfile        -> base image (gitleaks binary only)
#   containers/gitleaks-tests/Dockerfile  -> extends base + Python/pytest (test image)
#   docker-compose-files/gitleaks.yaml    -> `gitleaks` compose service (loop stage)
GITLEAKS_IMAGE ?= obsidian-timestamp-util-gitleaks:dev
GITLEAKS_VERSION ?= v8.18.4
GITLEAKS_COMPOSE ?= docker-compose-files/gitleaks.yaml
GITLEAKS_TESTS_COMPOSE ?= docker-compose-files/gitleaks-tests.yaml
GITLEAKS_TESTS_IMAGE ?= obsidian-timestamp-util-gitleaks-tests:dev

secret-scan-image: ## Build the gitleaks secret-scanning container image (base, for the loop stage).
	@echo "SECRET-SCAN: building $(GITLEAKS_IMAGE) (gitleaks $(GITLEAKS_VERSION))..."
	@nerdctl build -f containers/gitleaks/Dockerfile \
		--build-arg GITLEAKS_VERSION=$(GITLEAKS_VERSION) \
		-t $(GITLEAKS_IMAGE) . \
		|| docker build -f containers/gitleaks/Dockerfile \
		--build-arg GITLEAKS_VERSION=$(GITLEAKS_VERSION) \
		-t $(GITLEAKS_IMAGE) .

# Standalone secret scan (NOT a loop-harness stage). Runs the gitleaks repo scan
# containerized; the actual scan lives in the pre-commit hook (scripts/secret_scanner.py
# --staged) and CI (.github/workflows/trufflehog.yml). Kept as a Makefile target so it
# can be invoked on demand. Honours .gitignore + .gitleaks.toml allowlists.
# A detected secret fails (non-zero).
loop-secret-scan: ## gitleaks secret scan of the repo, containerized (docker compose only).
	@echo "LOOP-SECRET-SCAN: scanning repository with gitleaks (container)..."
	@rm -f .gitleaks-report.json
	@set +e; script -qec "docker compose -f $(GITLEAKS_COMPOSE) run --rm gitleaks" /dev/null >/dev/null 2>&1; RC=$$?; set -e; \
	if [ $$RC -ne 0 ] && [ -s .gitleaks-report.json ]; then \
		echo "LOOP-SECRET-SCAN: SECRETS DETECTED -- loop blocked."; \
		echo "LOOP-SECRET-SCAN: findings (file | rule | line):"; \
		python3 scripts/print_gitleaks_report.py .gitleaks-report.json || true; \
		rm -f .gitleaks-report.json; exit 1; \
	fi; \
	rm -f .gitleaks-report.json; \
	echo "LOOP-SECRET-SCAN: clean."

# MANDATORY loop-harness gate: run the secret-scanner's OWN pytest suite, containerized.
# Builds the gitleaks-tests image (real gitleaks + pytest) and runs
# tests/test_secret_scanner*.py inside the container (docker compose only, B9).
# Verifies the scanner's detection logic itself — no mocks on detection.
loop-secret-scan-tests: ## [LOOP] run secret-scanner pytest suite (containerized, real gitleaks).
	@echo "LOOP-SECRET-SCAN-TESTS: building test image + running suite (container)..."
	@$(MAKE) secret-scan-tests-image
	@script -qec "docker compose -f $(GITLEAKS_TESTS_COMPOSE) run --rm gitleaks-tests" /dev/null \
		|| { echo "LOOP-SECRET-SCAN-TESTS: tests FAILED -- loop blocked."; exit 1; }
	@echo "LOOP-SECRET-SCAN-TESTS: all passed."

# Non-scan helper: run the pytest suites that exercise the Python wrapper
# (developer/hook guard + real-gitleaks integration). Does NOT scan via Makefile.
test-secret-scanner: ## Run tests/test_secret_scanner*.py (wrapper/hook guard + integration).
	@echo "SECRET-SCAN: running pytest suites (tests/test_secret_scanner*.py)..."
	@python3 -m pytest tests/test_secret_scanner.py tests/test_secret_scanner_integration.py -v

# Test image build (extends base + pytest). Used by integration tests; not a scan command.
secret-scan-tests-image: ## Build the gitleaks + pytest test image.
	@echo "SECRET-SCAN: building test image (extends $(GITLEAKS_IMAGE))..."
	@$(MAKE) secret-scan-image
	@nerdctl build -f containers/gitleaks-tests/Dockerfile \
		-t $(GITLEAKS_TESTS_IMAGE) . \
		|| docker build -f containers/gitleaks-tests/Dockerfile \
		-t $(GITLEAKS_TESTS_IMAGE) .

.PHONY: secret-scan-image secret-scan-tests-image loop-secret-scan test-secret-scanner
