# obsidian-timestamp-utility Makefile — simplified inline nerdctl compose
# All loop stages: echo + single nerdctl compose command, proper exit codes.



# ---- Environment ----
REPO_NAME := obsidian-timestamp-utility
TAG       := $(shell node -p "require('./package.json').version")
HOST_UID  := $(shell id -u)
HOST_GID  := $(shell id -g)
export HOST_UID HOST_GID

LLAMA_MODEL      ?= qwen3.6-35b-a3b
LLAMA_CODE_MODEL ?= qwen3.6-35b-a3b
LLAMA_HOST       ?= http://localhost:11434

ISSUE_URL         ?= https://github.com/andyholst/obsidian-timestamp-utility/issues/20
TEST_FILTER       ?=
INTEGRATION_TEST_FILTER ?=
LLAMA_TIMEOUT    ?= 300
TYPE              ?=
CHANGE            ?= uuid-modal-agentic-generation
export TEST_FILTER INTEGRATION_TEST_FILTER LLAMA_TIMEOUT TYPE LLAMA_HOST CHANGE

HERMES_BIN      ?=
HERMES_MOUNT    ?=

RECORD_WORK_CMD ?= cd /project && export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/project/node_modules/.bin && git config --global --add safe.directory /project && python3 /project/scripts/record-work.py --change $(CHANGE) $(if $(DATE),--date $(DATE),)

# ---- Container runtime detection ----
DOCKER := $(shell \
	if command -v nerdctl >/dev/null 2>&1; then echo "nerdctl compose"; \
	elif command -v docker >/dev/null 2>&1; then echo "docker compose"; \
	else echo "docker compose"; fi)

# ---- TTY wrapper: script -q /dev/null for non-interactive, direct for interactive ----
# Usage: $(call tty_run,<compose-file>,<flags>,<service>,<cmd>)
define tty_run
	@if [ -t 1 ]; then \
		echo "  [tty] running interactively"; \
		$(DOCKER) -f $(1) $(2) $(3) $(4); \
	else \
		echo "  [non-tty] allocating PTY via script"; \
		script -q /dev/null $(DOCKER) -f $(1) $(2) $(3) $(4); \
	fi
endef

# ---- Permission floor (B9: rootless nerdctl) ----
b9-perms:
	@echo "B9: applying rootless nerdctl read/write permission floor..."
	@chmod -R a+rX . 2>/dev/null || true
	@for d in src backups openspec results agent-wiki tests; do \
		if [ -d "$$d" ]; then chmod -R a+rwX "$$d" 2>/dev/null || true; fi; \
	done
	@for f in CHANGELOG.md package.json manifest.json versions.json README.md src/__tests__/main.test.ts src/main.ts; do \
		if [ -f "$$f" ]; then chmod a+rw "$$f" 2>/dev/null || true; fi; \
	done
	@echo "B9: done."

# ---- Plugin build/test via containers/npm (tools.yaml) ----
build-app: b9-perms
	@echo "=== BUILD-APP: building plugin ==="
	$(call tty_run,docker-compose-files/tools.yaml,run --remove-orphans -e REPO_NAME=$(REPO_NAME) -e TAG=$(TAG),app,npm run build)
	@echo "BUILD-APP: done."

test-app: b9-perms
	@echo "=== TEST-APP: running jest ==="
	$(call tty_run,docker-compose-files/tools.yaml,run --remove-orphans -e REPO_NAME=$(REPO_NAME) -e TAG=$(TAG),app,npm test)
	@echo "TEST-APP: done."

# ---- Loop harness stages (11 stages per AGENTS.md B8) ----
# Stage order: collect -> ts-floor -> unit(mocked) -> unit-real(llama) -> e2e -> integration -> build-app -> test-app -> release-tests -> secret-scan-tests -> check-docs-sync

loop-collect: ## Gate 0: collection guard (dangling imports)
	@echo "=== LOOP [collect] collection guard ==="
	@echo "--- Collecting and running unit tests ---"
	$(DOCKER) -f docker-compose-files/agents.yaml run --remove-orphans -e TEST_FILTER="" unit-test-agents python -m pytest tests/unit/ -v
	@echo ""
	@echo "--- Collecting and running integration tests ---"
	$(DOCKER) -f docker-compose-files/agents.yaml run --remove-orphans -e TEST_FILTER="" integration-test-agents python -m pytest tests/integration/ -v
	@echo ""
	@echo "LOOP [collect]: clean."

loop-ts-floor: ## Gate 0.5: strict TS test/command floor vs origin/main
	@echo "=== LOOP [ts-floor] strict TS surface floor vs origin/main ==="
	bash scripts/ts_test_floor.sh
	@echo "LOOP [ts-floor]: passed."

loop-unit: ## Gate 1: mocked unit tests (hermetic, no llama)
	@echo "=== LOOP [unit] mocked unit tests ==="
	$(DOCKER) -f docker-compose-files/agents.yaml run --remove-orphans -e TEST_FILTER="" unit-test-agents python -m pytest tests/unit/ -q
	@echo "LOOP [unit]: passed."

loop-unit-real: ## Gate 2: real agent unit tests (live llama)
	@echo "=== LOOP [unit-real] real agent unit tests (llama) ==="
	$(DOCKER) -f docker-compose-files/agents.yaml run --remove-orphans unit-test-agents python -m pytest tests/unit/ -q
	@echo "LOOP [unit-real]: passed."

loop-e2e: ## Gate 3: standing e2e gates (ticket20 + ticket22 + greetings)
	@echo "=== LOOP [e2e] standing e2e gates ==="
	bash scripts/run_e2e_tests.sh
	@echo "LOOP [e2e]: passed."

loop-integration: ## Gate 4: broad agentic integration suite (B17)
	@echo "=== LOOP [integration] integration suite ==="
	bash scripts/run_integration_tests.sh
	@echo "LOOP [integration]: passed."

loop-build-app: ## Gate 5: build the plugin
	@echo "=== LOOP [build-app] building plugin ==="
	$(MAKE) --no-print-directory build-app
	@echo "LOOP [build-app]: passed."

loop-test-app: ## Gate 6: jest on the plugin
	@echo "=== LOOP [test-app] running jest ==="
	$(MAKE) --no-print-directory test-app
	@echo "LOOP [test-app]: passed."

loop-release-tests: b9-perms ## Gate 6.5: release-pipeline + README-sync dry-run tests
	@echo "=== LOOP [release-tests] release pipeline + README sync ==="
	$(DOCKER) -f docker-compose-files/agents.yaml run --remove-orphans -e DRY_RUN=1 -e GIT_CONFIG_GLOBAL=/tmp/gitconfig unit-test-agents sh -c "cd /project && DRY_RUN=1 python -m pytest tests/test_release_pipeline_dryrun.py tests/test_readme_sync.py tests/test_release_notes_bump.py -v"
	@echo "LOOP [release-tests]: passed."

loop-secret-scan-tests: b9-perms ## Gate 7: secret-scanner pytest suite (real gitleaks)
	@echo "=== LOOP [secret-scan-tests] building test image ==="
	$(DOCKER) -f docker-compose-files/gitleaks-tests.yaml run --remove-orphans unit-test-agents python -m pytest tests/test_secret_scanner*.py -v
	@echo "LOOP [secret-scan-tests]: passed."

check-docs-sync: b9-perms ## Gate 8 (FINAL B8): doc/loop sync gate
	@echo "=== CHECK-DOCS-SYNC: verifying docs alignment ==="
	$(DOCKER) -f docker-compose-files/agents.yaml run --remove-orphans -e GITHUB_TOKEN=$(GITHUB_TOKEN) -e CHANGE=$(CHANGE) -e TEST_FILTER="" unit-test-agents sh -c "cd /project && python3 /project/scripts/check-docs-sync.py"
	@echo "CHECK-DOCS-SYNC: passed."

# ---- Full loop harness: all stages in order ----
loop-harness: ## Run all loop stages in order (each exits 0 or fails)
	@echo "=== LOOP-HARNESS START ==="
	@echo "--- Stage 0: collect guard ---"
	$(MAKE) --no-print-directory loop-collect || { echo "FAIL: loop-collect"; exit 1; }
	@echo "--- Stage 0.5: ts-floor ---"
	$(MAKE) --no-print-directory loop-ts-floor || { echo "FAIL: loop-ts-floor"; exit 1; }
	@echo "--- Stage 1: unit (mocked) ---"
	$(MAKE) --no-print-directory loop-unit || { echo "FAIL: loop-unit"; exit 1; }
	@echo "--- Stage 2: unit-real (llama) ---"
	$(MAKE) --no-print-directory loop-unit-real || { echo "FAIL: loop-unit-real"; exit 1; }
	@echo "--- Stage 3: e2e gates ---"
	$(MAKE) --no-print-directory loop-e2e || { echo "FAIL: loop-e2e"; exit 1; }
	@echo "--- Stage 4: integration suite ---"
	$(MAKE) --no-print-directory loop-integration || { echo "FAIL: loop-integration"; exit 1; }
	@echo "--- Stage 5: build-app ---"
	$(MAKE) --no-print-directory loop-build-app || { echo "FAIL: loop-build-app"; exit 1; }
	@echo "--- Stage 6: test-app ---"
	$(MAKE) --no-print-directory loop-test-app || { echo "FAIL: loop-test-app"; exit 1; }
	@echo "--- Stage 6.5: release-tests ---"
	$(MAKE) --no-print-directory loop-release-tests || { echo "FAIL: loop-release-tests"; exit 1; }
	@echo "--- Stage 7: secret-scan-tests ---"
	$(MAKE) --no-print-directory loop-secret-scan-tests || { echo "FAIL: loop-secret-scan-tests"; exit 1; }
	@echo "--- Stage 8: check-docs-sync (B8) ---"
	$(MAKE) --no-print-directory check-docs-sync || { echo "FAIL: check-docs-sync"; exit 1; }
	@echo "=== LOOP-HARNESS COMPLETE: all gates green ==="

# ---- Agentic code generation (OpenSpec-driven, local, llama) ----
run-agentics: b9-perms ## Run AI agentics on a LOCAL OpenSpec change
	@test -n "$(CHANGE)" || { echo "ERROR: set CHANGE=<name>"; exit 1; }
	@echo "=== AGENTICS: running with llama=$(LLAMA_MODEL) change=$(CHANGE) ==="
	@mkdir -p backups
	@TS=$$(date +%Y%m%d-%H%M%S); \
	for f in src/main.ts src/__tests__/main.test.ts; do \
		if [ -f "$$f" ]; then \
			cp -p "$$f" "backups/$$(basename $$f).$$TS.bak" && echo "  BACKUP: $$f -> backups/$$(basename $$f).$$TS.bak"; \
		else \
			echo "  WARN: $$f not present, nothing to back up"; \
		fi; \
	done
	$(call tty_run,docker-compose-files/agents.yaml,run --remove-orphans -e CHANGE=$(CHANGE) -e GITHUB_TOKEN=$(GITHUB_TOKEN) -e LLAMA_HOST=$(LLAMA_HOST) -e LLAMA_REASONING_MODEL=$(LLAMA_MODEL) -e LLAMA_CODE_MODEL=$(LLAMA_CODE_MODEL) -e PROJECT_ROOT=/project,agents,ython -m prod.agentics openspec:$(CHANGE))
	@echo "=== AGENTICS: run complete ==="
	@ls -la src/main.ts src/__tests__/main.test.ts 2>/dev/null || echo "Note: generated files may be in a different location"
	@# OMISSION GUARD (B6): check if generated files shrank AND dropped contract command id
	@TS=$$(ls -1 backups/*.bak 2>/dev/null | head -1 | sed -E 's/.*\.([0-9]{8}-[0-9]{6})\.bak/\1/'); \
	CMD_ID=$$(grep -rhoE "id: '[^']+'" openspec/changes/$(CHANGE)/ 2>/dev/null | head -1 | sed -E "s/id: '([^']+)'/\1/"); \
	for f in src/main.ts src/__tests__/main.test.ts; do \
		bak=$$(ls -1 backups/$$(basename $$f).*.bak 2>/dev/null | tail -1); \
		if [ -f "$$f" ] && [ -n "$$bak" ]; then \
			before=$$(wc -c < "$$bak"); after=$$(wc -c < "$$f"); \
			if [ "$$after" -lt "$$before" ]; then \
				if [ -n "$$CMD_ID" ] && grep -q "$$CMD_ID" "$$f"; then \
					echo "OK: $$f shrank ($$before -> $$after) but contract command '$$CMD_ID' present — legitimate feature switch."; \
				else \
					echo "OMISSION DETECTED: $$f shrank ($$before -> $$after) and contract command '$$CMD_ID' missing. Restoring backup."; \
					cp -p "$$bak" "$$f"; \
					echo "ACTION: investigate why agentic code dropped content before re-running."; \
				fi; \
			else \
				echo "OK: $$f size $$before -> $$after bytes (no omission)."; \
			fi; \
		fi; \
	done

# ---- Phase 7: archive + work-log ----
phase7-archive: ## Archive an OpenSpec change (spec only) + auto-emit work-log
	@test -n "$(CHANGE)" || { echo "ERROR: set CHANGE=<name>"; exit 1; }
	@echo "Phase-7: work-log for $(CHANGE)"
	$(call tty_run,docker-compose-files/agents.yaml,run --remove-orphans -e GIT_CONFIG_GLOBAL=/tmp/gitconfig -e HERMES_PROFILE=project-manager,unit-test-agents,sh -c "$(RECORD_WORK_CMD) --emit-prompt /tmp/record-work.prompt")
	@if command -v hermes >/dev/null 2>&1; then \
		hermes profile use project-manager 2>/dev/null; \
		{ hermes -z "$$(cat /tmp/record-work.prompt)" > /tmp/record-work.prose 2>/dev/null; } || true; \
	fi
	$(call tty_run,docker-compose-files/agents.yaml,run --remove-orphans -e GIT_CONFIG_GLOBAL=/tmp/gitconfig -e HERMES_PROFILE=project-manager,unit-test-agents,sh -c "$(RECORD_WORK_CMD) --prose-file /tmp/record-work.prose")
	@rm -f /tmp/record-work.prompt /tmp/record-work.prose 2>/dev/null || true
	@echo "Phase-7: checking for open tasks in $(CHANGE)"
	$(call tty_run,docker-compose-files/agents.yaml,run --remove-orphans -e GIT_CONFIG_GLOBAL=/tmp/gitconfig,unit-test-agents,sh -c "python3 /project/scripts/assert_no_open_tasks_cli.py $(CHANGE)")
	@test -f agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py || { echo "FAIL(B1): e2e harness missing"; exit 1; }
	@echo "Phase-7: archiving spec for $(CHANGE)"
	@openspec archive -y $(CHANGE)
	@echo "Phase-7: done. No git commit/push performed."

# ---- Release automation ----
check-released: ## Guard: FAIL if current version already released or no semver gap
	@command -v node >/dev/null 2>&1 || { echo "CHECK: node required"; exit 1; }
	@VER=$$(node -p "require('./package.json').version"); \
	echo "CHECK-RELEASED: version = $$VER"
	@if ! command -v gh >/dev/null 2>&1; then echo "CHECK-RELEASED: gh not found — REFUSING"; exit 1; fi; \
	REMOTE=$$(git ls-remote --tags --refs origin 2>/dev/null | awk '{print $$2}' | sed 's#refs/tags/##' | sed 's/^v//' || true); \
	if echo "$$REMOTE" | grep -qx "$$VER"; then echo "CHECK-RELEASED: $$VER already released — bump BLOCKED"; exit 1; fi; \
	LATEST=$$(echo "$$REMOTE" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -t. -k1,1n -k2,2n -k3,3n | tail -1); \
	echo "CHECK-RELEASED: latest released = $${LATEST:-<none>}"; \
	if [ -n "$$LATEST" ]; then \
		ADV=$$(awk -F. -v c="$$VER" -v l="$$LATEST" 'BEGIN{split(c,a,".");split(l,b,".");for(i=1;i<=3;i++){if(a[i]>b[i]){print 0;exit};if(a[i]<b[i]){print 1;exit}}print 1}'); \
		if [ "$$ADV" != "0" ]; then echo "CHECK-RELEASED: $$VER does NOT advance past $$LATEST — bump BLOCKED"; exit 1; fi; \
	fi; \
	echo "CHECK-RELEASED: OK to bump."

bump-version: ## Bump Obsidian version (package.json + manifest.json + versions.json)
	@command -v node >/dev/null 2>&1 || { echo "BUMP: node required"; exit 1; }
	@command -v jq  >/dev/null 2>&1 || { echo "BUMP: jq required"; exit 1; }
	@if [ ! -f src/main.ts ]; then echo "BUMP: no src/main.ts — refusing"; exit 1; fi; \
	BASE=$$(git rev-parse --verify origin/main 2>/dev/null || echo "HEAD"); \
	if git diff --quiet $$BASE -- src/main.ts && [ -z "$$(git ls-files --others --exclude-standard src/main.ts)" ]; then \
		echo "BUMP: no new TS vs $$BASE — refusing"; exit 1; \
	fi; \
	echo "BUMP: new TS detected, bumping..."
	OLD=$$(node -p "require('./package.json').version"); \
	if [ "$$PART" != "patch" ] && [ "$$PART" != "minor" ] && [ "$$PART" != "major" ]; then echo "BUMP: PART must be patch|minor|major"; exit 1; fi; \
	IFS='.' read -r MAJ MIN PAT <<< "$$OLD"; \
	if [ "$$PART" = "major" ]; then MAJ=$$((MAJ+1)); MIN=0; PAT=0; \
	elif [ "$$PART" = "minor" ]; then MIN=$$(MIN+1); PAT=0; \
	else PAT=$$((PAT+1)); fi; \
	NEW="$$MAJ.$$MIN.$$PAT"; \
	echo "BUMP: $$OLD -> $$NEW (PART=$$PART)"; \
	node -e "const f='package.json';const j=require('./'+f);j.version='$$NEW';require('fs').writeFileSync(f,JSON.stringify(j,null,2)+'\n');"; \
	node -e "const f='manifest.json';const j=require('./'+f);j.version='$$NEW';require('fs').writeFileSync(f,JSON.stringify(j,null,2)+'\n');"; \
	TMP=$$(mktemp); \
	jq --arg v "$$NEW" --arg m "$$(node -p "require('./manifest.json').minAppVersion")" '. + {$$v:$$m}' versions.json > "$$TMP" && mv "$$TMP" versions.json; \
	echo "BUMP: done."

tag-release: ## Create LOCAL git tag v<version> (NO push)
	@command -v node >/dev/null 2>&1 || { echo "TAG: node required"; exit 1; }
	@VER=$$(node -p "require('./package.json').version"); \
	TAG="v$$VER"; \
	if git rev-parse "$$TAG" >/dev/null 2>&1; then echo "TAG: $$TAG exists — skipping"; exit 0; fi; \
	git tag -a "$$TAG" -m "Release $$VER"; \
	echo "TAG: created local tag $$TAG (NOT pushed)."

release-notes: ## Refresh README release-notes block
	@command -v node >/dev/null 2>&1 || { echo "RELNOTES: node required"; exit 1; }
	$(call tty_run,docker-compose-files/agents.yaml,,unit-test-agents,sh -c "cd /project && python3 /project/scripts/update-release-notes.py README.md")

changelog: b9-perms ## Generate CHANGELOG.md
	@echo "Generating CHANGELOG.md..."
	$(call tty_run,docker-compose-files/agents.yaml,run --remove-orphans -e GIT_CONFIG_GLOBAL=/tmp/gitconfig,unit-test-agents,/project/scripts/gen_changelog.sh) || echo "changelog skipped"
	@$(MAKE) --no-print-directory changelog-format

changelog-format: b9-perms ## Normalise CHANGELOG.md with Prettier
	@echo "Normalising CHANGELOG.md..."
	$(call tty_run,docker-compose-files/agents.yaml,run --remove-orphans -e GIT_CONFIG_GLOBAL=/tmp/gitconfig,unit-test-agents,sh -c "cd /project && git config --global --add safe.directory /project && node_modules/.bin/prettier --write CHANGELOG.md") || echo "changelog-format skipped"

bump-from-changelog: b9-perms ## Rename '## Unreleased' -> next version
	@echo "Bumping version from changelog..."
	$(call tty_run,docker-compose-files/agents.yaml,run --remove-orphans -e GIT_CONFIG_GLOBAL=/tmp/gitconfig,unit-test-agents,sh -c "cd /project && git config --global --add safe.directory /project && python3 /project/scripts/bump_from_changelog.py") || echo "bump-from-changelog skipped"
	@$(MAKE) --no-print-directory changelog-format

# ---- Release flows ----
release-flow: ## Canonical local release flow: squash -> bump -> changelog -> release-notes (NO push)
	@set -e; \
	echo "=== RELEASE-FLOW START ==="; \
	$(MAKE) --no-print-directory squash-commits; \
	$(MAKE) --no-print-directory bump-local PART=$(PART); \
	$(MAKE) --no-print-directory changelog; \
	$(MAKE) --no-print-directory release-notes; \
	echo "=== RELEASE-FLOW COMPLETE ==="

bump-local: check-released ## LOCAL-ONLY: bump + tag (no squash/changelog/push)
	@set -e; \
	echo "=== BUMP-LOCAL ==="; \
	$(MAKE) --no-print-directory bump-version PART=$(PART); \
	$(MAKE) --no-print-directory tag-release; \
	echo "=== BUMP-LOCAL COMPLETE ==="

# ---- Squash commits (typed Conventional commit, commitlint-gated) ----
squash-commits: ## Squash all commits ahead of main into ONE typed Conventional commit
	@if [ "$${ALLOW_SQUASH:-0}" = "1" ]; then \
		echo "B30d: ALLOW_SQUASH=1 — overriding pre-PR squash guard."; \
	else \
	BRANCH=$$(git rev-parse --abbrev-ref HEAD 2>/dev/null); \
	if command -v gh >/dev/null 2>&1 && [ -n "$$GH_TOKEN" ]; then \
		PRJSON=$$(gh pr view "$$BRANCH" --json number,comments,reviews 2>/dev/null); \
		if [ -n "$$PRJSON" ]; then echo "B30: $$BRANCH has open PR — SQUASH FORBIDDEN"; exit 1; fi; \
		echo "B30: $$BRANCH is pre-PR — squash allowed."; \
	elif [ -n "$$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)" ]; then \
		echo "B30: $$BRANCH tracks remote — SQUASH FORBIDDEN"; exit 1; \
	else \
		echo "B30: gh/token unavailable — skipping guard (fail-open)."; \
	fi; \
	fi
	@MAIN=$$(git rev-parse --verify origin/main 2>/dev/null || git rev-parse --verify main 2>/dev/null || echo ""); \
	if [ -z "$$MAIN" ]; then echo "COMMIT: no 'main' ref — aborting"; exit 1; fi; \
	AHEAD=$$(git rev-list --count $$MAIN..HEAD 2>/dev/null || echo 0); \
	if [ "$$AHEAD" = "0" ] && [ -z "$$(git diff HEAD --name-only)" ]; then echo "COMMIT: nothing ahead of main — nothing to squash"; exit 0; fi; \
	echo "COMMIT: $$AHEAD commits ahead of main — squashing"; \
	git reset --soft $$MAIN; \
	git add -A; \
	FILES=$$(git diff --cached --name-only $$MAIN); \
	STAT=$$(git diff --stat $$MAIN | tail -40); \
	echo "COMMIT: asking Hermes for typed Conventional message..."; \
	hermes profile use project-manager >/dev/null 2>&1 || true; \
	PROMPT="Write ONE git commit in Conventional Commits style. FIRST line: type(scope): subject (type in feat|fix|docs|refactor|perf|test|chore|build|ci|style|revert). Then blank line + thorough body (~72 cols). Files changed: $$(printf '\n%s' $$FILES)"; \
	MSG=$$(hermes -z "$$PROMPT" 2>/dev/null); \
	if [ -z "$$MSG" ]; then echo "COMMIT: no message from Hermes — aborting"; git reset --quit $$MAIN >/dev/null 2>&1 || true; exit 1; fi; \
	FIRST=$$(printf '%s' "$$MSG" | head -1); \
	if ! printf '%s' "$$FIRST" | grep -qE '^(feat|fix|docs|refactor|perf|test|chore|build|ci|style|revert)(\([^)]*\))?:[[:space:]]'; then \
		echo "COMMIT: FAIL-CLOSED — untyped first line: '$$FIRST'"; \
		git reset --quit $$MAIN >/dev/null 2>&1 || true; exit 1; \
	fi; \
	if ! printf '%s\n' "$$MSG" | "$(CURDIR)/node_modules/.bin/commitlint" --config "$(CURDIR)/commitlint.config.cjs"; then \
		echo "COMMIT: FAIL-CLOSED — message failed commitlint"; \
		git reset --quit $$MAIN >/dev/null 2>&1 || true; exit 1; \
	fi; \
	git commit -m "$$MSG" && echo "COMMIT: created typed Conventional commit (commitlint-passed, not pushed)."

# ---- OpenSpec change scaffolding ----
openspec-new: b9-perms ## Scaffold an OpenSpec change via the openspec CLI
	@test -n "$(NAME)" || { echo "ERROR: NAME required. Run: make openspec-new NAME=<kebab-name>"; exit 1; }
	@echo "=== OPENSPEC-NEW: scaffolding $(NAME) ==="
	@bash scripts/scaffold-openspec-change.sh --name $(NAME) $(if $(DESC),--desc "$(DESC)",) $(if $(GOAL),--goal "$(GOAL)",) $(if $(CAPABILITY),--capability $(CAPABILITY),)
	@echo "=== OPENSPEC-NEW complete: review openspec/changes/$(NAME)/ ==="

# ---- Worktree delivery ----
wt-create: ## Create an isolated git worktree for an OpenSpec change
	@test -n "$(NAME)" || { echo "ERROR: NAME required"; exit 1; }
	@REPO_ROOT=$$(git rev-parse --show-toplevel); WT=$$REPO_ROOT/worktrees/$(NAME); \
	if [ -d "$$WT" ]; then echo "WT-CREATE: $$WT exists — reuse it."; \
	else git worktree add "$$WT" -b wt/$(NAME) && echo "WT-CREATE: created $$WT"; fi; \
	if [ ! -e "$$WT/node_modules" ] && [ -d "$$REPO_ROOT/node_modules" ]; then ln -s ../../node_modules "$$WT/node_modules"; fi; \
	echo "WT-CREATE: done."

openspec-flow: ## Agent-driven change lifecycle in a worktree
	@test -n "$(NAME)" || { echo "ERROR: NAME required"; exit 1; }
	@bash scripts/openspec-change-flow.sh --name $(NAME) $(if $(PUSH),--push,) $(if $(NO_AGENTICS),--no-agentics,) $(if $(NO_LOOP),--no-loop,)

# ---- Python linting/formatting (via container) ----
lint-python: ## Run ruff linting on Python code
	@echo "Linting Python with ruff..."
	$(call tty_run,docker-compose-files/agents.yaml,,unit-test-agents,ruff check /app/src) || echo "ruff reported issues"

format: ## Format Python code with ruff
	@echo "Formatting Python with ruff..."
	$(call tty_run,docker-compose-files/agents.yaml,,unit-test-agents,ruff format agents/agentics/src) || true

# ---- Agentic test targets ----
test-agents-unit-mock: ## Mocked unit tests (fast, no llama)
	@echo "Running mocked unit tests..."
	$(DOCKER) -f docker-compose-files/agents.yaml run --remove-orphans -e TEST_FILTER=$(TEST_FILTER) unit-test-agents python -m pytest tests/unit/ -q
	@echo "Mock unit tests done."

test-agents-unit: ## Unit tests for agents (llama)
	@echo "Running unit tests for agents (llama)..."
	$(DOCKER) -f docker-compose-files/agents.yaml run --remove-orphans unit-test-agents python -m pytest tests/unit/ -q
	@echo "Unit tests done."

test-agents-integration: ## Full integration tests (needs GITHUB_TOKEN + llama)
	@echo "Running integration tests..."
	$(DOCKER) -f docker-compose-files/agents.yaml run --remove-orphans -e GITHUB_TOKEN=$(GITHUB_TOKEN) -e "TEST_FILTER=$(INTEGRATION_TEST_FILTER)" integration-test-agents
	@echo "Integration tests done."

test: test-app test-agents ## All tests (app + agents)

# ---- Miscellaneous ----
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-35s\033[0m %s\n", $$1, $$2}'

stop-containers: ## Stop all project containers (excludes honcho)
	@if command -v nerdctl >/dev/null 2>&1; then \
		CIDS=$$(nerdctl ps -q --filter label=com.docker.compose.project 2>/dev/null); \
		REMAINING=""; \
		for cid in $$CIDS; do \
			CNAME=$$(nerdctl inspect "$$cid" --format '{{.Name}}' 2>/dev/null | sed 's|^/||'); \
			case "$$CNAME" in honcho-*) ;; *) REMAINING="$$REMAINING $$cid";; esac; \
		done; \
		REMAINING=$$(echo "$$REMAINING" | xargs); \
		if [ -n "$$REMAINING" ]; then nerdctl stop $$REMAINING 2>/dev/null; echo "Stopped project containers."; else echo "No project containers to stop."; fi; \
	elif command -v docker >/dev/null 2>&1; then \
		CIDS=$$(docker ps -q --filter label=com.docker.compose.project 2>/dev/null); \
		REMAINING=""; \
		for cid in $$CIDS; do \
			CNAME=$$(docker inspect "$$cid" --format '{{.Name}}' 2>/dev/null | sed 's|^/||'); \
			case "$$CNAME" in honcho-*) ;; *) REMAINING="$$REMAINING $$cid";; esac; \
		done; \
		REMAINING=$$(echo "$$REMAINING" | xargs); \
		if [ -n "$$REMAINING" ]; then docker stop $$REMAINING 2>/dev/null; echo "Stopped project containers."; else echo "No project containers to stop."; fi; \
	else \
		echo "No container runtime found — skipping."
	fi

clean: ## Full clean
	@echo "Cleaning up..."
	rm -rf dist release results coverage node_modules || true

clean-cache: ## Remove Python caches only
	find . -name "__pycache__" -type d -exec rm -rf {} + || true
	rm -rf .pytest_cache
	find . -name ".pytest_cache" -type d -exec rm -rf {} + || true

clean-logs: ## Remove all logs
	find . -name "logs" -type d -exec rm -rf {} + 2>/dev/null || true
	find . \( -name "*.logs" -o -name "*.log" \) -delete 2>/dev/null || true

nuke-containers: ## Stop and remove ALL containers, networks, volumes
	@echo "=== NUKE: starting ==="
	@HONCHO_COMPOSE="$(HONCHO_COMPOSE)" PROJECT_COMPOSE_DIR="$(PROJECT_COMPOSE_DIR)" bash scripts/nuke-all-containers.sh
	@echo "=== NUKE: done ==="

# ---- Requirements regeneration ----
generate-requirements: ## Regenerate requirements.txt from requirements.in
	@echo "Generating requirements from requirements.in..."
	$(call tty_run,docker-compose-files/pip.yaml,,pip,)
	@echo "Regenerated agents/agentics/requirements.txt"

.PHONY: help all build-app test-app lint-python format \
        test-agents-unit test-agents-unit-mock test-agents-integration \
        run-agentics phase7-archive openspec-new wt-create openspec-flow \
        loop-harness loop-collect loop-ts-floor loop-unit loop-unit-real \
        loop-e2e loop-integration loop-build-app loop-test-app \
        loop-release-tests loop-secret-scan-tests check-docs-sync \
        loop-tasks loop-verify loop-trigger \
        squash-commits bump-version release-notes tag-release \
        changelog changelog-format bump-from-changelog \
        check-released release-prep release-flow bump-local \
        lint-commits install-git-hooks \
        nuke-containers generate-requirements \
        stop-containers clean clean-cache clean-logs \
        b9-perms deliver-change record-work record-work-prompt \
        pr-resolve pr-comment pr-resolve-and-comment
