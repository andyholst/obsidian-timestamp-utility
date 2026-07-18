# Timestamp Plugin Changelog

This changelog tracks updates to the Obsidian Timestamp Utility plugin, which allows users to insert timestamps and rename files with timestamp prefixes in Obsidian.

## 0.4.15
### ✨ New Features

- **feat(loop): B26 — agent may commit/push own branch after loop gate is green; B12 worktree-PR delivery (#55)**
  - * feat(pr): enforce no-squash and no-revert governance on open PRs
  - This change codifies the agent's PR delivery governance as durable
  - loop-harness behaviours (B27-B30) and wires the worktree-confined
  - delivery flow into the OpenSpec pipeline. The motivation: open PRs
  - were being destabilised by squash/revert operations that broke the
  - human review workflow. The agent now delivers verified work as a
  - branch-pushed PR and forbids history-rewriting once a PR is live.
  - Loop-harness durable behaviours
  - B27 (openspec-change-flow): on completion (all tasks.md boxes
  - ticked + loop gate green + hook pass) the agent auto-promotes
  - wt/<name> -> feat/<name>, pushes, and opens the PR with no second
  - prompt. Delivery is always a PR push, never a file copy back into
  - the parent tree.
  - B28 (pr-review-no-squash): squash is forbidden once a PR is open /
  - under review. It is only permitted while still local and pre-PR.
  - B29 (pr-agent-comment-resolve): a red gate after push drives a
  - forward fixup commit plus an agent PR comment; never revert,
  - squash, or reset.
  - B30 (pr-fix-no-revert): reverting commits is never allowed on any
  - branch, especially a PR. Fixes are forward normal commits.
  - HARD rule (B28a/B30): revert forbidden on pushed/open PRs; squash
  - forbidden post-push. Correct failures forward, not backwards.
  - Agentic pipeline / delivery scripts
  - scripts/openspec-change-flow.sh (new, 156 lines): scaffolds the
  - OpenSpec change inside a dedicated worktree, runs agentic
  - generation + the loop gate there, archives on green, and (with
  - PUSH=1) delivers by pushing feat/<name> as the PR. All artifacts
  - stay in the worktree; the parent tree is never touched.
  - scripts/pr_comment.sh (new, 45 lines): posts the agent's
  - resolution comment on the PR red-gate.
  - scripts/pr_resolve.sh (new, 68 lines): drives the forward-fixup +
  - comment-resolve flow for an open PR.
  - scripts/regen_doc_sync_fixtures.py: updated fixture regeneration.
  - Execution / Makefile / compose
  - Makefile gains openspec-flow / openspec-redeliver targets and the
  - worktree-confined delivery wiring.
  - docker-compose-files/worktree-override.yaml (new): compose override
  - for worktree-confined container execution.
  - scripts/run-loop-harness.sh: stage-order tweaks kept in sync.
  - OpenSpec specs merged
  - agent-branch-governance, openspec-change-flow, pr-agent-comment-resolve,
  - pr-fix-no-revert, pr-review-stability, and readme-worktree-flow-doc
  - are merged into openspec/specs, each with proposal/tasks/spec.
  - Docs / sync (B8)
  - AGENTS.md, docs/openspec-engineering-loop-harness.md and
  - hermes/skills/openspec-loop-harness.md are updated and kept in
  - agreement. check-docs-sync now detects richer drift: B-behaviour
  - range gaps, stage reordering, removed stages, and en-dash/ascii
  - variants, backed by new fixtures under tests/fixtures/check_docs_sync.
  - Tests / versioning
  - tests/test_check_docs_sync.py extended to cover the new drift
  - fixtures (in_sync, drift_b_range_low, drift_reorder,
  - drift_stage_removed, in_sync_ascii, in_sync_en_dash).
  - src/__tests__/main.test.ts adjusted to the new command contract.
  - package.json / manifest.json / versions.json bumped.
  - agent-wiki entries recorded for the no-squash review and the
  - uuid-modal agentic generation work.
  - * docs(changelog): regenerate CHANGELOG from squashed PR governance commit
  - regenerated via make changelog after squashing B28 B29 B30 B30d into one commit
  - no behaviour change; changelog only
  - * feat(pr): add PR stability & worktree-flow governance
  - Introduce PR lifecycle governance that keeps an open PR stable while still
  - letting the human override it deliberately.
  - PR stability (B28/B29/B30):
  - Squash is forbidden once a PR is open/under review (B28a); the squash
  - gate refuses while a branch is pushed or a PR is open.
  - Revert is forbidden on any branch once pushed/open (B30); a red gate
  - after push is fixed by a forward fixup commit, never revert/squash/reset.
  - PR review comments are resolved by actually commenting back on the PR
  - (B29a): scripts/pr_comment.sh and scripts/pr_resolve.sh post the
  - resolution so the loop closes the thread instead of only editing code.
  - Explicit override (squash-override-flag): when the human sets
  - ALLOW_SQUASH=1 / force-push, the governance is overridden on purpose; the
  - spec documents the override path so it is a recorded exception, not a hole.
  - Agent branch governance (B27): the agent must prompt for the target
  - branch before promoting; on completion (tasks ticked + loop green + hook
  - pass) it auto-promotes wt/<name> -> feat/<name>, pushes, and opens the PR
  - with no second prompt.
  - OpenSpec change/worktree flow (openspec-change-worktree-flow): every change
  - gets its own linked worktree; delivery is the PR push (never a file copy
  - back to the parent) and corrections redeliver via force-with-lease to the
  - same PR branch. scripts/openspec-change-flow.sh orchestrates new -> worktree
  -> generate -> verify -> archive -> deliver, with
  - docker-compose-files/worktree-override.yaml isolating each change via
  - COMPOSE_PROJECT_NAME=otu-<name>.
  - Loop-harness sync (B8): AGENTS.md, docs/openspec-engineering-loop-harness.md
  - and hermes/skills/openspec-loop-harness.md are kept in lockstep on the
  - canonical 10-stage order (loop-collect -> ... -> check-docs-sync) and the
  - B1-B30 behaviours. The check-docs-sync fixture set (in_sync, in_sync_ascii,
  - in_sync_en_dash, drift_b_range_low, drift_reorder, drift_stage_removed) and
  - tests/test_check_docs_sync.py were regenerated to assert drift on stage
  - order, B-behaviour range, and the OLLAMA_HOST-only live-test skip rule.
  - scripts/run-loop-harness.sh and scripts/regen_doc_sync_fixtures.py reflect
  - the same order.
  - Docs: agent-wiki entries record each change's verification-against-spec and
  - README documents the worktree flow. manifest.json/package.json/versions.json
  - bumped accordingly; src/__tests__/main.test.ts updated to match.

- **feat(loop): enforce host-background make exec and reviewed-squash PR delivery**
  - Mandate that long-running verification targets execute on the REAL host via
  - terminal(background=true) instead of the foreground sandbox, and formalize
  - the reviewed-squash release flow that auto-delivers a PR. Both OpenSpec
  - changes are merged into the standing specs.
  - Loop-harness execution model (docker-make-pipeline spec)
  - AGENTS.md and the loop skill now state explicitly that every long-running
  - `make` target (run-agentics, build-app, test-app, loop-harness, loop-e2e,
  - deliver-change, phase7-archive, release-flow) MUST be launched through
  - terminal(background=true), which runs on the host where docker/rootless
  - nerdctl/live Ollama live. The foreground sandbox at /workspace has no
  - docker/nerdctl and reporting `docker: command not found` is expected and
  - NOT a blocker. This removes the "can't run from here" failure mode.
  - The Makefile gains the docker-make-pipeline wiring that drives verification
  - exclusively through docker compose on the host (no Dagger, no MCP), matching
  - the documented B19 host/background split between the sandbox and host mounts.
  - Reviewed-squash release automation (release-automation spec)
  - B27: when a change's tasks.md is fully ticked, the loop gate is green, and
  - the docs-sync/hook pass, the harness auto-promotes wt/<name> -> feat/<name>,
  - pushes origin feat/<name>, and opens the PR with no second prompt. Delivery
  - is the PR push, never a file copy back into the parent tree (B12 override).
  - Red gate after push -> forward fixup commit (B29a PR comment, B30), never
  - revert/squash/reset. The one exception: post-PR squash+force is allowed only
  - via `make loop-final BRANCH=<feat> APPROVED=1` after explicit human approval
  - ('PR looks great'), which re-runs a fresh green loop-harness then squashes,
  - regenerates the changelog, and force-with-leases. `squash-commits`/
  - `loop-finish` guard fail-open when there is no upstream tracking so they are
  - never run against an open PR.
  - B22 release automation stays a post-green loop-engineering stage, never part
  - of the 10-stage verification gate, and never pushes.
  - Docs-sync discipline (B8)
  - AGENTS.md, docs/openspec-engineering-loop-harness.md, the openspec-loop-
  - harness skill, and scripts/run-loop-harness.sh are kept in agreement on the
  - canonical 10-stage order (loop-collect -> loop-ts-floor -> loop-unit ->
  - loop-unit-real -> loop-e2e -> loop-integration -> loop-build-app ->
  - loop-test-app -> loop-secret-scan-tests -> check-docs-sync), the
  - loop-ts-floor guard, the B1-B31 behaviour range, and the live-test skip rule
  - (OLLAMA_HOST only, not GITHUB_TOKEN).
  - Added check_docs_sync test fixtures covering in-sync, ascii/en-dash variants,
  - and three drift cases (B-range low, stage reorder, stage removed) so the
  - guard fails closed on any desync.
  - Merged specs
  - openspec/specs/docker-make-pipeline/spec.md and openspec/specs/release-
  - automation/spec.md are merged from the archived changes
  - 2026-07-18-make-always-background and 2026-07-18-loop-final-reviewed-squash.
  - Changelog
  - Recorded agent-wiki/2026-07-18-make-always-background.md and linked it from
  - agent-wiki/index.md.

## 0.4.14


### ✨ New Features

- **feat(pr): enforce no-squash and no-revert governance on open PRs**
  - This change codifies the agent's PR delivery governance as durable
  - loop-harness behaviours (B27-B30) and wires the worktree-confined
  - delivery flow into the OpenSpec pipeline. The motivation: open PRs
  - were being destabilised by squash/revert operations that broke the
  - human review workflow. The agent now delivers verified work as a
  - branch-pushed PR and forbids history-rewriting once a PR is live.
  - Loop-harness durable behaviours
  - B27 (openspec-change-flow): on completion (all tasks.md boxes
  - ticked + loop gate green + hook pass) the agent auto-promotes
  - wt/<name> -> feat/<name>, pushes, and opens the PR with no second
  - prompt. Delivery is always a PR push, never a file copy back into
  - the parent tree.
  - B28 (pr-review-no-squash): squash is forbidden once a PR is open /
  - under review. It is only permitted while still local and pre-PR.
  - B29 (pr-agent-comment-resolve): a red gate after push drives a
  - forward fixup commit plus an agent PR comment; never revert,
  - squash, or reset.
  - B30 (pr-fix-no-revert): reverting commits is never allowed on any
  - branch, especially a PR. Fixes are forward normal commits.
  - HARD rule (B28a/B30): revert forbidden on pushed/open PRs; squash
  - forbidden post-push. Correct failures forward, not backwards.
  - Agentic pipeline / delivery scripts
  - scripts/openspec-change-flow.sh (new, 156 lines): scaffolds the
  - OpenSpec change inside a dedicated worktree, runs agentic
  - generation + the loop gate there, archives on green, and (with
  - PUSH=1) delivers by pushing feat/<name> as the PR. All artifacts
  - stay in the worktree; the parent tree is never touched.
  - scripts/pr_comment.sh (new, 45 lines): posts the agent's
  - resolution comment on the PR red-gate.
  - scripts/pr_resolve.sh (new, 68 lines): drives the forward-fixup +
  - comment-resolve flow for an open PR.
  - scripts/regen_doc_sync_fixtures.py: updated fixture regeneration.
  - Execution / Makefile / compose
  - Makefile gains openspec-flow / openspec-redeliver targets and the
  - worktree-confined delivery wiring.
  - docker-compose-files/worktree-override.yaml (new): compose override
  - for worktree-confined container execution.
  - scripts/run-loop-harness.sh: stage-order tweaks kept in sync.
  - OpenSpec specs merged
  - agent-branch-governance, openspec-change-flow, pr-agent-comment-resolve,
  - pr-fix-no-revert, pr-review-stability, and readme-worktree-flow-doc
  - are merged into openspec/specs, each with proposal/tasks/spec.
  - Docs / sync (B8)
  - AGENTS.md, docs/openspec-engineering-loop-harness.md and
  - hermes/skills/openspec-loop-harness.md are updated and kept in
  - agreement. check-docs-sync now detects richer drift: B-behaviour
  - range gaps, stage reordering, removed stages, and en-dash/ascii
  - variants, backed by new fixtures under tests/fixtures/check_docs_sync.
  - Tests / versioning
  - tests/test_check_docs_sync.py extended to cover the new drift
  - fixtures (in_sync, drift_b_range_low, drift_reorder,
  - drift_stage_removed, in_sync_ascii, in_sync_en_dash).
  - src/**tests**/main.test.ts adjusted to the new command contract.
  - package.json / manifest.json / versions.json bumped.
  - agent-wiki entries recorded for the no-squash review and the
  - uuid-modal agentic generation work.

- **feat(pr): add PR stability & worktree-flow governance**
  - Introduce PR lifecycle governance that keeps an open PR stable while still
  - letting the human override it deliberately.
  - PR stability (B28/B29/B30):
  - Squash is forbidden once a PR is open/under review (B28a); the squash
  - gate refuses while a branch is pushed or a PR is open.
  - Revert is forbidden on any branch once pushed/open (B30); a red gate
  - after push is fixed by a forward fixup commit, never revert/squash/reset.
  - PR review comments are resolved by actually commenting back on the PR
  - (B29a): scripts/pr_comment.sh and scripts/pr_resolve.sh post the
  - resolution so the loop closes the thread instead of only editing code.
  - Explicit override (squash-override-flag): when the human sets
  - ALLOW_SQUASH=1 / force-push, the governance is overridden on purpose; the
  - spec documents the override path so it is a recorded exception, not a hole.
  - Agent branch governance (B27): the agent must prompt for the target
  - branch before promoting; on completion (tasks ticked + loop green + hook
  - pass) it auto-promotes wt/<name> -> feat/<name>, pushes, and opens the PR
  - with no second prompt.
  - OpenSpec change/worktree flow (openspec-change-worktree-flow): every change
  - gets its own linked worktree; delivery is the PR push (never a file copy
  - back to the parent) and corrections redeliver via force-with-lease to the
  - same PR branch. scripts/openspec-change-flow.sh orchestrates new -> worktree
    -> generate -> verify -> archive -> deliver, with
  - docker-compose-files/worktree-override.yaml isolating each change via
  - COMPOSE_PROJECT_NAME=otu-<name>.
  - Loop-harness sync (B8): AGENTS.md, docs/openspec-engineering-loop-harness.md
  - and hermes/skills/openspec-loop-harness.md are kept in lockstep on the
  - canonical 10-stage order (loop-collect -> ... -> check-docs-sync) and the
  - B1-B30 behaviours. The check-docs-sync fixture set (in_sync, in_sync_ascii,
  - in_sync_en_dash, drift_b_range_low, drift_reorder, drift_stage_removed) and
  - tests/test_check_docs_sync.py were regenerated to assert drift on stage
  - order, B-behaviour range, and the OLLAMA_HOST-only live-test skip rule.
  - scripts/run-loop-harness.sh and scripts/regen_doc_sync_fixtures.py reflect
  - the same order.
  - Docs: agent-wiki entries record each change's verification-against-spec and
  - README documents the worktree flow. manifest.json/package.json/versions.json
  - bumped accordingly; src/**tests**/main.test.ts updated to match.

### 📝 Documentation

- **docs(changelog): regenerate CHANGELOG from squashed PR governance commit**
  - regenerated via make changelog after squashing B28 B29 B30 B30d into one commit
  - no behaviour change; changelog only

## 0.4.13


### ✨ New Features

- **feat(loop): add openspec intake gate, lint hook, docs-sync guards (#53)**
  - Add a request-to-openspec intake gate that converts inbound work
  - requests into OpenSpec changes of record before any implementation
  - runs. Per-channel triggers: the Hermes dashboard always converts;
  - Telegram and terminal CLI convert only when the message contains the
  - keyword "openspec" (case-insensitive); Kanban-delivered tasks still
  - scaffold an OpenSpec change via `make openspec-new` rather than relying
  - on kanban tooling alone. The gate is an agent instruction only — the
  - erroneous `request_intake.py` in `agents/agentics/` was removed, so the
  - Python pipeline never performs intake. The new capability is codified in
  - `openspec/specs/request-intake/spec.md` (generated from the
  - `request-to-openspec` change) and mirrored in AGENTS.md,
  - `hermes/skills/openspec-loop-harness.md`, and
  - `docs/openspec-engineering-loop-harness.md` per the B8 bidirectional
  - sync rule.
  - Introduce a trailing-whitespace lint guard: `git-hooks/pre-commit`
  - auto-strips trailing whitespace from staged text files and never exits
  - non-zero, so it is inert under the agentic loop (which performs no git
  - commit). `make install-git-hooks` wires both `commit-msg` (Conventional
  - Commit lint) and the new `pre-commit` into `.git/hooks`. The behaviour is
  - specified in `openspec/specs/lint-trailing-whitespace/spec.md`.
  - Strengthen the B8 doc-sync guard (`make check-docs-sync`, the final loop
  - stage) with fixtures under `tests/fixtures/check_docs_sync/`: in_sync,
  - in_sync_ascii, and in_sync_en_dash (all pass — en-dash/ascii variants of
  - the B-range are treated as equivalent), plus negative cases
  - drift_b_range_low, drift_reorder, and drift_stage_removed that must fail
  - the guard. This proves the sync check detects disagreements on the
  - 8-stage order, the `loop-ts-floor` guard, and the B1–B25 behaviour
  - range across AGENTS.md, the skill mirror, the technical reference, and
  - the loop runner — closing the drift that let docs silently disagree.
  - Align README with the actual commit history and add an architecture
  - overview. `readme-align-with-commits` and `readme-architecture-overview`
  - specs drive updates to README.md, `docs/AGENTIC_ARCHITECTURE.md`, and
  - `docs/openspec-engineering-loop-harness.md`; the merged specs live under
  - `openspec/specs/readme-alignment/`, `readme-align-with-commits/`, and
  - `readme-architecture-overview/`.
  - Refresh the durable behaviour set in AGENTS.md and the skill mirror
  - (B1–B25), recording the deterministic `code_integrator` floor, the
  - no-commit/no-push gates, the worktree-only edit rule, and the
  - release-automation post-green stage. Version metadata is advanced in
  - manifest.json, package.json, and versions.json, `src/__tests__/main.test.ts`
  - is updated, and each change is documented under `agent-wiki/` with the
  - backlog kept in `agent-wiki/index.md`.

- **feat(secret-scan): replace TruffleHog with gitleaks and add loop gate**
  - Replace the broken TruffleHog GitHub Action with gitleaks as the
  - project's secret scanner and wire it into the OpenSpec loop-harness as
  - a first-class, containerized verification stage with real tests.
  - Detection engine and config
  - Add scripts/secret_scanner.py, which delegates 100% of detection to
  - the gitleaks binary (no homemade regex/entropy). It supports
    --staged (pre-commit), --message-file (commit-msg), and --path
  - (on-demand) modes and fails closed on a detected secret.
  - Add .gitleaks.toml using `[extend] useDefault = true` plus a
  - repo-local allowlist covering test fixtures, docs, and dependency /
  - build caches (.venv, node_modules, **pycache**, .env, .git) so the
  - default ruleset is never silently disabled.
  - Add scripts/print_gitleaks_report.py, which renders each finding as
  - `file | rule | line` so a block is never an opaque "secrets
  - detected" message.
  - Containers, compose, and Makefile gates
  - Add containers/gitleaks/Dockerfile and containers/gitleaks-tests/
  - Dockerfile (real gitleaks + pytest) plus docker-compose-files/
  - gitleaks.yaml and gitleaks-tests.yaml.
  - Extend the Makefile with `loop-secret-scan-tests` (canonical loop
  - entry), `secret-scan-image`, `secret-scan-tests-image`, and the
  - on-demand `loop-secret-scan` / `check-secrets` alias. Docker compose
  - only, consistent with the rest of the harness (no Dagger, no MCP).
  - Loop-harness integration
  - Update scripts/run-loop-harness.sh to insert the `loop-secret-scan-
  - tests`stage between`loop-test-app`and the final`check-docs-sync`,
  - keeping the canonical 8(+2) stage order in sync with the Makefile.
  - Dev-side hooks and CI
  - Add git-hooks/pre-commit (runs `secret_scanner.py --staged`) and
  - git-hooks/commit-msg (runs `--message-file`); both reject a commit
  - that contains or messages a secret. Installed via `make
  - install-git-hooks`.
  - Replace .github/workflows/trufflehog.yml with a gitleaks workflow
  - (gitleaks/gitleaks-action@v2, fetch-depth: 0, GITLEAKS_CONFIG).
  - Tests (no mocks on detection)
  - Add tests/test_secret_scanner.py (hermetic unit) and tests/
  - test_secret_scanner_integration.py (real gitleaks binary, no mocks)
  - to exercise the scanner's detection logic every loop run.
  - Specs and docs-sync (B8)
  - Merge openspec/specs/secret-scan/spec.md and openspec/specs/loop-
  - secret-scan/spec.md from the four archived changes
  - (replace-trufflehog-with-gitleaks, loop-harness-secret-scan,
  - secret-scan-show-findings, secret-scanner-loop-tests).
  - Keep AGENTS.md, hermes/skills/openspec-loop-harness.md,
  - docs/openspec-engineering-loop-harness.md, and run-loop-harness.sh in
  - agreement on stage order, the loop-ts-floor guard, the B1-B25
  - behaviours, and the live-test skip rule (OLLAMA_HOST only).
  - Add agent-wiki entries documenting the migration and the visible-
  - findings behaviour.
  - Credential hygiene: only documented example shapes (e.g. AKIA…EXAMPLE,
  - xoxb-…) appear in tests; no real keys are committed.

## 0.4.12


### ✨ New Features

- **feat(loop): add release automation, doc-sync and TS-floor gates (#52)**
  - Establish the OpenSpec loop-harness as a deterministic, spec-driven
  - engineering discipline (behaviours B1-B25) and ship the release and
  - verification machinery that implements it. The LLM generator is now
  - constrained by a deterministic floor and corrected by a closed loop gate
  - that must pass before any change is declared done.
  - Agentic pipeline (agents/agentics/src)
  - code_integrator_agent.py: the deterministic merge floor is now the sole
  - writer of src/main.ts. It parses the spec contract (id/command name/
  - Modal class) from the OpenSpec change, string-only strips any
  - non-contract addCommand and existing Modal of that name from both the
  - file and the LLM output, then injects the authoritative contract command
  - body and appends the spec Modal + generator only if absent (idempotent).
  - The LLM never holds the pen (B7/B10/B11).
  - openspec_loader.py: contract resolution now also matches the date-prefixed
  - archived change dir (archive/YYYY-MM-DD-<name>, B19); repo root is resolved
  - by probing for a dir that contains openspec/changes rather than a fixed
  - relative depth, so the e2e harness runs against the real /project mount
  - instead of falsely skipping (false-skip-audit-and-root-fix).
  - Release automation (B22/B23)
  - Makefile: squash-commits forces a valid type(scope): first line and passes
  - it through commitlint (lint-commits gate), restoring pre-squash state on
  - failure; bump-from-changelog advances patch past max(released tags, HEAD);
  - loop-finish runs assert-backlog-clear -> archive-all -> squash -> changelog
    -> bump -> format, no push; release-flow / release-prep / loop-release added.
  - scripts: gen_changelog.sh, merge_changelog.py (dedup vs committed HEAD),
  - bump_from_changelog.py, assert_no_open_tasks_cli.py (archive gate fails
  - closed on any open - [ ] task, B16), record-work.py containerized.
  - CHANGELOG sections are now driven by the squashed commit's Conventional
  - type (feat/fix/docs/refactor/chore) instead of hand authoring.
  - Verification gates (now mandatory loop stages)
  - scripts/check-docs-sync.py: final loop stage asserting AGENTS.md,
  - hermes/skills/openspec-loop-harness.md, docs/...loop-harness.md,
  - Makefile, scripts/run-loop-harness.sh and the e2e gates all agree on the
  - 8-stage order + final check-docs-sync, the loop-ts-floor guard and the
  - B1-B25 range. Hermetic mutation tests under tests/ (real fixture copies,
  - regen_doc_sync_fixtures.py, test_check_docs_sync.py) flip green<->red on
  - in-sync vs drifted fixtures.
  - scripts/ts_test_floor.sh: FAILS if the branch's describe/leaf it/test/
  - jest-collected/addCommand counts drop below origin/main (silent
  - feature/test-removal guard, ts-test-floor spec).
  - Docker / Makefile hardening (B9)
  - Makefile docker_run macro rewritten for .ONESHELL: no longer ends recipes
  - with a bare `exit` that silently dropped later lines; non-tty runs use a
  - `script -qec` PTY wrap so nerdctl's forced --tty never deadlocks. RECORD_WORK
  - uses a literal node_modules/.bin PATH that no longer clobbers git.
  - scripts/run-loop-harness.sh streams each stage live, prints a start banner
  - and heartbeat on quiet stages, and ends with a per-stage PASS/FAIL summary.
  - containers/agents/Dockerfile and docker-compose-files/agents.yaml updated
  - for the rootless-nerdctl bind-mount perms floor and correct /project mount.
  - Workflow / behaviours (B1-B25)
  - worktree-per-openspec-change: each change gets its own linked worktree
  - sandbox; phase7-archive now runs containerized record-work and merges the
  - spec only (never commits/pushes, B4/B14).
  - base64-tool and uuid-modal agentic generation land as new specs with
  - standing e2e coverage (test_base64_e2e_integration.py,
  - test_change_driven_ts_generation_e2e.py); greetings e2e proves the
  - deterministic floor injected a feature absent from the committed baseline.
  - Merged OpenSpec specs: loop-finish-make-target, loop-harness-integrity,
  - openspec-workflow, record-work, release-automation, ts-test-floor, doc-sync,
  - base64-tool, docker-run, false-skip-audit-and-root-fix. Updated
  - AGENTS.md / hermes skill / docs to mirror all behaviour changes (B8 sync).
  - manifest.json, package.json and versions.json bumped; README + CHANGELOG
  - refreshed.

- **feat(loop): add request-intake gate, lint hook, and docs-sync fixtures**
  - Add the OpenSpec request-intake gate plus supporting lint, README, and
  - docs-sync work, all driven through the spec-driven loop:
  - Request-intake gate (openspec/specs/request-intake/spec.md, from the
  - request-to-openspec change): new per-channel discipline that turns an
  - inbound request into an OpenSpec change of record via `make openspec-new`
  - /`openspec new change` before any implementation. Triggers are per-channel:
  - the Hermes dashboard always converts; Telegram and the terminal CLI convert
  - only when the message/text contains "openspec" (case-insensitive), and
  - messages without it are exempt. A request delivered as a Kanban task still
  - requires the agent to scaffold the OpenSpec change rather than limiting
  - itself to kanban tooling. This is an agent instruction only — the earlier
  - request_intake.py was removed from agents/agentics.
  - Trailing-whitespace lint (openspec/specs/lint-trailing-whitespace/spec.md,
  - git-hooks/pre-commit): a pre-commit hook that strips trailing whitespace
  - from staged text files and never exits non-zero, so it is inert under the
  - loop (which performs no git commit). Installed via `make install-git-hooks`.
  - README alignment + architecture overview (openspec/specs/readme-alignment,
  - openspec/specs/readme-architecture-overview; README.md,
  - docs/AGENTIC_ARCHITECTURE.md, docs/openspec-engineering-loop-harness.md):
  - brought README and architecture docs in line with actual committed
  - behaviour, grouped docs into subfolders, and added an architecture overview.
  - Loop-harness engineering + B8 sync (AGENTS.md, Makefile,
  - hermes/skills/openspec-loop-harness.md,
  - docs/openspec-engineering-loop-harness.md): kept the sync set consistent on
  - the deterministic code_integrator floor (sole writer of src/main.ts; the LLM
  - only proposes raw candidate text), the B1–B25 durable behaviours, the
  - 8-stage loop order (loop-collect → loop-ts-floor → loop-unit →
  - loop-unit-real → loop-e2e → loop-integration → loop-build-app →
  - loop-test-app), and the final `check-docs-sync` stage that fails closed if
  - any sync doc disagrees on stage order, the loop-ts-floor guard, or the
  - B-behaviour range.
  - Docs-sync drift fixtures (tests/fixtures/check_docs_sync/\*): added
  - in_sync / in_sync_ascii / in_sync_en_dash / drift_reorder /
  - drift_stage_removed / drift_b_range_low fixture triples (AGENTS.md,
  - docs/openspec-engineering-loop-harness.md, hermes/skills/openspec-loop-harness.md)
  - to prove the B8 drift detector catches reorderings, stage removals, and
  - B-range drift while tolerating ASCII/en-dash variants.
  - agent-wiki entries (agent-wiki/index.md + 2026-07-16-\* entries): recorded
  - the lint-fix, readme-align, readme-architecture, and request-to-openspec
  - work with verification against spec.

## 0.4.11


### ✨ New Features

- **feat(loop): add commitlint-gated squash-commits and release automation**
  - Implement the OpenSpec loop-harness engineering discipline end-to-end and
  - harden the release automation that the branch is built around.
  - Deterministic generation floor
  - code_integrator_agent.py now runs as the SOLE writer of src/main.ts in
  - every mode (incl. fast/TEST_FAST_MODE), so the spec contract is always
  - injected even when the npm test phase is skipped (B7.1). The integrator
  - strips non-contract addCommand calls and stale Modals, then injects the
  - authoritative contract command body verbatim; no generated TS bodies live
  - in Python (B10). On failure the loop fixes the spec, restores the backup,
  - and re-runs — never hand-editing TS (B11).
  - openspec_loader.py resolves the repo root by probing for a dir that
  - contains openspec/changes (never a fixed depth), handles archived
  - date-prefixed change dirs (archive/\*-<name>), and scaffolds GitHub-issue
  - changes via `openspec new change ticket<N>` (B15).
  - Eight-stage loop gate
  - Makefile defines loop-harness = loop-collect -> loop-ts-floor ->
  - loop-unit -> loop-unit-real -> loop-e2e -> loop-integration ->
  - loop-build-app -> loop-test-app, plus phase7-archive with an open-task
  - guard (B16) and the standing B1 e2e guard.
  - ts_test_floor.sh (new) fails the current branch if its describe/leaf
  - it/test/addCommand counts drop below origin/main (silent feature/test
  - removal guard, ts-test-floor spec).
  - run-loop-harness.sh streams each stage live and prints a PASS/FAIL/
  - timeout summary.
  - Release automation (release-automation spec, +366 lines)
  - squash-commits now FORCES a typed `type(scope):` first line and passes
  - it through commitlint (lint-commits gate); on failure it restores the
  - pre-squash state (git reset --quit <main>) and creates no commit.
  - changelog sections are derived from the squashed commit's Conventional
  - type (feat->..., fix->..., docs->..., refactor->..., chore->...) via
  - gen_changelog.sh; merge_changelog.py merges idempotently, deduping
  - against committed git HEAD rather than appending duplicate sections.
  - bump_from_changelog.py computes a STABLE next version (max of released
  - remote tags + committed pkg/versions at HEAD, ignoring local working
  - tags) so re-runs overwrite in place instead of runaway 0.4.11->0.4.12.
  - loop-finish, release-guard, release-finalisation-commands,
  - changelog-commit-alignment and loop-green-auto-squash-changelog provide
  - the green-gated one-command finalisation (squash -> changelog -> bump ->
  - format), NO push (B4/B14/B22).
  - git-hooks/commit-msg wires commitlint into every manual commit.
  - Generated feature + tests
  - src/main.ts / src/**tests**/main.test.ts gain the base64-tool command,
  - Modal and generator (base64-tool spec) and the stricter test-floor wiring.
  - New test_base64_e2e_integration.py covers the base64 tool;
  - test_change_driven_ts_generation_e2e.py root-resolution fix removes a
  - false `src/main.ts` skip (B19) so the contract e2e actually runs.
  - Durable behaviours & docs
  - AGENTS.md, hermes/skills/openspec-loop-harness.md and
  - docs/openspec-engineering-loop-harness.md are re-synced (B8) across the
  - full B1-B25 set: per-change worktrees (B24), no parent reset (B24),
  - no agent squash without approval (B25), false-skip audit (B17),
  - live Ollama tests run rather than skip (B18/B19).
  - manifests bumped: manifest.json, package.json, versions.json.
  - agent-wiki captures the strict-ts-test-floor entry; CHANGELOG.md updated.

## 0.4.9


### ✨ New Features

- **add task command to convert reminders to calendar tasks**
- **add new "Convert Reminders to Date Time-Blocked Tasks" command**
- **implement folder selection modal with fuzzy search interface**
- **Create taskProcessor.ts with reminder parsing and time-blocking**
- **add comprehensive unit tests for task processing functionality**
- **process reminders in format "- [ ] Task (@YYYY-MM-DD HH:MM)" to time-blocked tasks**
- **Organize tasks by date in daily files (YYYY-MM-DD.md)**
- **Preserve existing checked tasks and merge with new ones**
- **Use Obsidian's file system API for folder and file operations**

### 📝 Documentation

- **update README.md with new command documentation**

## 0.4.8


### ✨ New Features

- **refactored Makefile to run containerd**
- **Added Bash script to make system containerd migration enabled.**

### 🔧 Refactor Improvements

- **removed Docker Compose dependency since new Docker/NerdCtl has it integrated.**
- **Makefile uses containerd cmd to run and build images.**

### 📝 Documentation

- **updated README.md file based on the new containerd bash wrapper script.**

## 0.4.7


### ✨ New Features

- **implement the code integrator agent**
- **make sure code integrator preserve the existing TypeScript code with new TS code.**
- **make sure code integrator preserve existing TS tests with new tests.**

### 🔧 Refactor Improvements

- **refactored away the mocks of the LLM agents so they are being unit tested for reals.**
- **fetching GitHub tickets and writing to files has been mocked in unit tests.**
- **use qwen2.5-coder instead of qwen2.5 LLM model.**
- **added more logging to enable better troubleshooting in case of errors.**
- **made the code generator more strict to generate TS code and TS tests accordingly.**
- **simplified the code integrator to only deal with 2 files, no so much llm prompting.**
- **updated code extractor to only deal with main.ts and it's main.test.ts file.**
- **refine the llm agents to reduce halicunation.**
- **added new test asserts to cover up for refactored agents code and python code.**
- **added more real unit tests based on refactored llm agents.**
- **be able to silent the logs to debug level to give clarity for real exceptions for failure.**
- **improved the unit tests to run reall LLM agents excepty for the fetch integrator agent.**
- **get the updated unit tests running with real LM except for fetch ticket agent.**
- **added more edge unit test cases to verify that the TS code/tests is intact.**
- **refactored the integration tests to copver the new refactored LLM code.**

## 0.4.6


### ✨ New Features

- **added Code Extractor Agent**
- **added code extractor agent code and tests.**
- **updated the unit test to make make code extractor agent work with real files.**
- **added asserts of the expected real relevant files to integration tests.**
- **added corner cases for the integration test for the CodeExtractorAgent.**

### 🔧 Refactor Improvements

- **improve the build time to execute the tests with specific requirements.**
- **always run Pre Test Runner Agent first to make TS test works before creating new code.**

## 0.4.5


### ✨ New Features

- **implement clarify ticket agent**
- **the TicketClarityAgent has been implemented to clarify existing ticket.**
- **ticket with clear title, desc, requirements & acceptance criteria for coding agents.**
- **TicketClarityAgent will set better conditions to generate TS code and tests for other agents.**

## 0.4.4


### ✨ New Features

- **added Pre-Test Runner Agent**

### 🛠️ Maintenance

- **cleaned up unnessesary comments.**

## 0.4.3


### ⚡ Performance Improvements

- **added test coverage of the Obsidian plugin code**

## 0.4.2


### ✨ New Features

- **added Code Generation Agent Logic**
- **added code generation agent to create code and tests based on ticket description.**
- **added updated the tests to verify that TypeScript code/tests is generated.**
- **created State class to manage data between agents.**
- **setup LangGraph workflow to automate the analysis process.**

### 🐞 Bug Fixes

- **fixed the llm prompt operation to use the recommended operation.**

### 🔧 Refactor Improvements

- **refactored out FetchIssueAgent to fetch and validate GitHub issue content.**
- **refactored out ProcessLLMAgent to analyze ticket content using an LLM.**
- **implemented OutputResultAgent to log analysis results.**
- **updated the unit and integration tests for the system.**
- **renamed the package to agentics to make more sense.**
- **updated the Makefile and Docker Compose since the Python package has been renamed.**

### 📝 Documentation

- **updated the README.md file based on the updated Makefile.**

## 0.4.1


### ✨ New Features

- **implemented Ticket interpreter Node**
- **add python ticket interpreter to read GitHub tickets to work with other agents.**

### 📝 Documentation

- **updated the README.md file how to run the agents and test them.**

## 0.4.0


### ✨ New Features

- **added new code logic**
- **added rename filename logic to make sure filename is the same as the title.**

### 🔧 Refactor Improvements

- **reduced boiler plate code from main.ts file.**

### 📝 Documentation

- **updated the README to include the new rename filename command based on file title.**

## 0.3.1


### 🐞 Bug Fixes

- **aligned with modern Obsidian plugin standards**
- **replaced assume what file you edit code with actual file you edit on code.**

## 0.3.0


### ✨ New Features

- **added generate a list of YYYY-MM-DD dates logic**
- **implemented generate range list of dates with happy/unhappy tests.**

### 📝 Documentation

- **updated README.md file how to use the generate the date range list.**

## 0.2.0


### ✨ New Features

- **add rename file with timestamp & heading**
- **Implemented the new command to rename specific file with timestamp prefix & title as filename**

### 📝 Documentation

- **updated README.md file how to use the new rename command with timestamp & title as filename**

## 0.1.8


### 🐞 Bug Fixes

- **forgot to push the simplified release.sh**

### 📝 Documentation

- **forgot to push the simplified release.sh file to generate latest tag release notes**

## 0.1.7


### 🐞 Bug Fixes

- **fixed automatic release for pr merge**
- **simplified the release.sh to generate release notes based on CHANGELOG.md file**

## 0.1.6


### 🐞 Bug Fixes

- **updated release workflow and release script**
- **the release workflow didn't see any commit changes, so no proper release notes was created**
- **updated make to update package-lock accordingly**

## 0.1.5


### 🐞 Bug Fixes

- **did a tag release for Obsidian plugin release**
- **the release script should work as supposed to**

## 0.1.4


### 🐞 Bug Fixes

- **fixed commit linting for current branch**
- **fixed commit linting so only commits for the current branch is being linted**

## 0.1.3


### 🐞 Bug Fixes

- **fixed proper version tagging to comply with Obsidian plugin release policy**

## 0.1.2


### 🐞 Bug Fixes

- **publish to Obsidian community with correct version**
- **bumped the version of the Timestamp Utility to be released for the Obsidian community**

## 0.1.1


### ✨ New Features

- **add changelog log. & integrated with release**
- **added new Makefile section to generate/update CHANGELOG.md file**

### 🐞 Bug Fixes

- **updated the release script to only gen. release notes accordingly**
- **fixed the release.sh script to have proper spacing between sections and lists**
- **renamed the release timestamp artifact with proper filename**

### ⚡ Performance Improvements

- **improved the release and commit GitHub workflow actions**

### 🔧 Refactor Improvements

- **refactored the release script**
- **update release workflow action to publish the correct**

### 📝 Documentation

- **created new CHANGELOG.md file**

### 🛠️ Maintenance

- **added missings versions.json file for Obsidian plugin**

## 0.1.0


### ✨ New Features

- **implemented file renaming with timestamp prefix for filename**
- **implemented YYYYMMDDHHmmss timestamp at file cursor**
- **added Docker and Docker Compose for consistent build and test environments**
- **configured GitHub workflows for automated testing and release**

### 🐞 Bug Fixes

- **generation of changelog for pr merge (#5)**
- **resolved changelog generation errors for multi-type commits**
- **release pipeline**
- **corrected changelog release template**

### ⚡ Performance Improvements

- **improve release script efficiency for changelog categorization**

### 🔧 Refactor Improvements

- **simplified TimestampPlugin command structure in main.ts**

### 📝 Documentation

- **documented installation steps and prerequisites in README**
- **added usage instructions for timestamp commands in README**

### 🛠️ Maintenance

- **configured Jest testing suite with Obsidian API mocks**
- **added unit tests for timestamp insertion and file renaming commands**
- **added Makefile with build, test, and release tasks**
- **enable commitlint for conventional commit validation**
- **set up git-chglog for automated changelog generation**
- **remove unused mock utilities and clean up test setup**
