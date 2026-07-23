# OpenSpec Loop Harness (obsidian-timestamp-utility)

Project-specific skill for working in `obsidian-timestamp-utility`. It encodes the
behaviour defined in `AGENTS.md` and `docs/openspec-engineering-loop-harness.md`.
Load this whenever you touch an OpenSpec change, the Makefile, `containers/`, or run
the agentic pipeline in this repo.

## Fundamentals — harness engineering vs loop engineering (read first)
The whole system is a concrete implementation of two disciplines. Grasp these before the detail.
- **The core problem:** an LLM is a *non-deterministic generator*. It drifts (near-misses like
  `insert-random-id` vs the spec's `insert-uuid-v7`), omits existing logic on regen, hallucinates
  imports/APIs/tests, and is unrepeatable. You cannot ship by trusting raw LLM output directly.
- **Harness engineering = *constrain* the generator into a verifiable shape.** A harness is the
  deterministic scaffolding (a "jig") around the LLM that forces its output into a known-good form:
  a **single source of truth** (the OpenSpec `## Contract`/`## Test Contract` — never TS in Python,
  B10); the **LLM never holds the pen** (the `CodeIntegratorAgent` string-merge floor is the sole
  writer of `src/main.ts`; the LLM only proposes raw text — B7/B11); **bounded, checkable output**
  (idempotent contract injection, omission guard, git-HEAD restore B5/B6); and **one reproducible
  execution path** (docker compose, pinned `requirements.in`, B9 perms floor). It makes an
  unreliable generator produce reliable artifacts.
- **Loop engineering = *correct* the generator across attempts until an objective gate passes.**
  A closed feedback loop with four parts: (1) **generate** (run the pipeline), (2) **verify** with
  an objective gate that defines "done" (`make build-app` exit 0 + `make test-app` pass + spec
  walk), (3) **diagnose & correct by fixing the SOURCE OF TRUTH not the symptom** (edit the spec,
  restore, re-run — never hand-edit generated TS, B11; each pass a *different* tweak), and
  (4) **terminate** (bounded ~5 attempts, then escalate to fixing the Python floor B13). Durable
  invariants B1–B31 are the loop's "laws of physics" that never regress on any pass.
- **How they fit:** the harness is the **floor** (nothing worse can be written); the loop is the
  **ratchet** (each pass only moves toward green, invariants never slip). Full write-up:
  `docs/openspec-engineering-loop-harness.md` §0.

## Hard constraints (never violate)
- **No Dagger, no MCP.** All execution is `docker compose` only:
  `docker-compose-files/*.yaml` + `containers/<svc>/Dockerfile`.
  The `agentics` service reads the LOCAL OpenSpec change (`openspec:<name>`); it does
  NOT fetch GitHub (unless you deliberately run an integration test that needs `GITHUB_TOKEN`).
- **`requirements.txt` is ALWAYS regenerated — never hand-edited.** The single source
  of truth is `docker-files/pip-requirements/requirements.in`. Run
  `make generate-requirements` to compile it into `agents/agentics/requirements.txt`
  (via the `containers/pip` pip-compile image). If `docker compose build agentics`
  fails with a `ResolutionImpossible` conflict, FIX IT IN THE `.in` FILE (e.g. pin a
  transitive dep there) and re-run `make generate-requirements`. Do NOT patch the
  generated `requirements.txt` by hand.
- **Docker volume mounts are resolved against the CWD, not the compose-file dir.** When
  `make run-agentics` runs from a *worktree*, relative `../...` paths resolve to the
  worktree, not the repo. The `agentics` service MUST mount the Python source as an
  **absolute** path (`/home/asimov/repository/git/projects/obsidian-timestamp-utility/agents/agentics/src:/app/prod`)
  and the `app` service MUST bind-mount `node_modules` absolutely
  (`.../obsidian-timestamp-utility/node_modules:/app/node_modules`) because a symlink
  inside `/app` points outside the container's mount and breaks.
- **Rootless nerdctl remaps the container uid, so bind-mounted files land as "other".**
  Make the worktree world-writable (`chmod -R a+rwX <worktree>`) so the container can
  write `src/main.ts`, `/project/results`, `backups/`. The agentic *source* tree must be
  world-readable (`chmod -R a+rX agents/agentics/src`) or import fails with PermissionError.
- **Generated TS MUST be an Obsidian Modal registered as a command.** Every feature the
  pipeline emits MUST be an `obsidian.Modal` subclass wired via `this.addCommand({ id,
  name, callback: () => new <Feature>Modal(this.app).open() })`. The integration is done
  by a **deterministic string merge** in `CodeIntegratorAgent.integrate_code_deterministic`
  (append classes, inject `addCommand` into `onload`, add imports) — never an LLM full-file
  rewrite (that caused omission). The merge MUST consume the trailing `);` of each
  `this.addCommand({...});` block or `tsc` fails with `TS1005`.
- **Exact spec contract:** the uuid change's `tasks.md` 3.3.0 pins the generator to
  `id: 'insert-uuid-v7'`, `name: 'Insert UUID v7 (timestamp-based)'`, `UuidV7Modal` class.
  Tighten `tasks.md` with an explicit "exact contract" bullet whenever spec-adherence
  drifts (the LLM otherwise emits a near-miss like `insert-random-id`).

## Phase flow (from AGENTS.md)
0. Structure already scaffolded (`openspec/`, `containers/`, `worktrees/`, `agent-wiki/`).
1. **Propose:** create the change with the real `openspec` CLI (B15 — never hand-write the
   directory). The reproducible harness wraps exactly this CLI step and seeds the conventional
   files:
   `make openspec-new NAME=<kebab> [CAPABILITY=<cap>] [DESC="..."] [GOAL="..."]` →
   write `proposal.md` (Why / What / Capabilities / Impact) and, per capability,
   `specs/<cap>/spec.md` in delta format: `## ADDED Requirements` →
   `### Requirement: <name>` (MUST/SHALL) → `#### Scenario:` with `- **WHEN**` / `- **THEN**`.
   Optionally `design.md`. (Manual equivalent: `openspec new change <kebab>`.)
   Get templates via `openspec instructions proposal --change <name>` /
   `openspec instructions tasks --change <name>`.
2. **Tasks:** `tasks.md` as a checkbox plan (`- [ ] X.Y ...`). These are the executable
   steps the agentic pipeline reads.
3. **Validate:** `openspec validate <name>` (and `openspec status --change <name>`).
   Do NOT implement until it passes.
4. **Worktree:** `git worktree add ../worktrees/<name> -b feat/<name>`; `cd` into it.
   Work ONLY the change's tasks.
5. **Backup + Generate:** `make run-agentics CHANGE=<name>` from the worktree.
   - It timestamp-backs up `src/main.ts` + `src/__tests__/main.test.ts` into `backups/`
     BEFORE generating (safety net; `backups/` is git-ignored).
   - The pipeline ingests `proposal.md`+`tasks.md`+`specs/**` (via
     `agents/agentics/src/openspec_loader.py`) and regenerates those two TS files.
   - **Omission guard (contract-aware).** If a generated file is SMALLER than its backup, the
     Makefile checks whether the spec's contract command id (parsed from the change's
     `tasks.md`/`spec.md`) is still present. A shrink is only a *genuine* omission when the
     command id is MISSING AND the file shrank — a legitimate feature switch (e.g. greetings
     test < uuid test) produces a different-sized file, so pure byte-size is a false positive.
     If the contract id is present, it is a successful generation — never restored. Only when the
     id is missing does it auto-restore the backup and flag it. When that happens, investigate
     WHY the Python agentic code dropped content (inspect `code_integrator` / `main_agent` /
     `code_extractor` write logic and the `export_name` deterministic-assembly rules) and fix
     the root cause before re-running. Never ship a shrunk file.
6. **Verify (loop engineering):** `make build-app` (must exit 0) → `make test-app`
   (jest must pass). Walk every `### Requirement` / `#### Scenario` / Acceptance
   Criterion and confirm it. If build/test fails, loop (re-run agentics / fix /
   re-verify) — do not declare done until green. Be strict and honest.
7. **Document + decide:** `make phase7-archive CHANGE=<name>` auto-emits the
   Phase-7 work-log — after `openspec archive` succeeds it runs `scripts/record-work.py`, writing
   `agent-wiki/YYYY-MM-DD-<name>.md` (Verification Against Spec per requirement) and updating
   `agent-wiki/index.md`. No separate `make record-work` call is needed (it remains callable
   standalone for re-runs). This is the scriptable replacement for the never-created `record-work`
   skill — `scripts/record-work.py` drafts the prose via the project-manager Hermes CLI. If all
   tasks done AND verification passes → `openspec archive <name>` (via `make phase7-archive`), then
   merge/remove the worktree. Otherwise state what's missing.

## Key commands
- `openspec new change <name>` / `openspec validate <name>` / `openspec archive <name>`
- `make build-app` / `make test-app`  (via `docker-compose-files/tools.yaml` → `containers/npm`; `node_modules` is bind-mounted absolutely)
- `make run-agentics CHANGE=<name>`  (via `docker-compose-files/agents.yaml` → `containers/agents`; auto backups + omission guard; Python source mounted at `/app/prod`)
- `make test-agents-unit` (real logic) / `make test-agents-integration` (real llama/GitHub) / `make verify-agentics-after-run` (re-runs unit+integration after generation) / `make test-agents-collect` (CI collection guard: `pytest --collect-only` unit+integration, fails fast on dangling imports)
- `make test-agents-real` (real-logic unit + real integration) / `make generate-requirements`

## Known pitfalls (learned the hard way)
- **`nerdctl` `docker compose run` REQUIRES a PTY ("provided file is not a console" trap).**
  Rootless nerdctl's `compose run` always injects `--tty` and fails with
  `provided file is not a console` whenever the container's stdout is a bare file or
  pipe (e.g. `make … > log`, or piping through `tee`). Fix: the stage runner wraps
  `make` in `script -qec "make <stage>; echo \$? > rcfile" /dev/null 2>&1 | tee -a log`
  so `make` (and its `docker compose run` children) get a real PTY, `tee` drains it to
  the terminal + log, and make's REAL exit code is captured via the `rcfile` marker
  (piping through `tee` alone would mask the rc as 0 = false green).
  **DO NOT** wrap each `docker compose run` in its own `script -qec` AND then `tail -f`
  the log file — the `tail -f` reads the file but never drains the `script` PTY, so
  the PTY buffer fills, the container blocks, and under an interactive TTY job control
  sends SIGSTOP (process state `T`) → the loop HANGS at stage 0. Also DO NOT use
  `</dev/null` on the run command (false green: the `test-agents-*` targets' trailing
  `@echo` exits 0 even when `docker compose` fails). Keep all `docker compose run`
  commands as PLAIN `docker compose -f … run --rm …` and let the runner provide the PTY
  via `setsid script -qec "make <stage>; echo \$? > rcfile" /dev/null 2>&1 | tee -a log`
  — the `setsid` detaches `script` from the interactive shell's job control so it can't
  be SIGSTOP'd (this is what makes it work under a REAL interactive terminal without
  hanging). Capture make's real rc via the `rcfile` marker (tee alone masks it).
  The `docker compose run` commands themselves live in Makefile `$(call docker_run, …)`,
  which runs PLAIN when stdout is a tty (interactive shell OR the loop runner's `setsid
  script`) and falls back to `script -qec` only when stdout is NOT a tty (CI / piped /
  redirected) — so the container always gets a console yet PTYs are never nested (nested
  PTYs under job control = SIGSTOP deadlock).
- `docker compose build agentics` needs `HOST_UID`/`HOST_GID` args with a fallback
  (`${HOST_UID:-1000}`) — passing an empty string overrides the Dockerfile default and
  breaks `groupadd`/`useradd`.
- pip-compile on this graph (torch + transformers + langchain + langgraph + mcp) is SLOW
  (5–15+ min) and only writes `requirements.txt` once the full solve completes. Run it
  in the background with `notify_on_complete`; it is not stuck.
- The agentics container has no `ps`, but you can confirm progress from the host with
  `ps -eo pid,etimes,pcpu,comm --sort=-pcpu | grep pip`.
- Work in `/home/asimov/repository/git/projects/obsidian-timestamp-utility` — NOT the
  `/workspace` decoy bind mount.
- **`build-app`/`test-app` fail with `jest: not found` / `rollup: not found`** in a
  worktree → the worktree has no `node_modules` and the `app` compose mounts the worktree
  as `/app`. Fix: bind-mount the repo `node_modules` absolutely into the `app` service
  (`tools.yaml`: `- <repo>/node_modules:/app/node_modules`). A symlink does NOT work
  (target is outside the container mount).
- **`src/main.ts` `TS1005: ',' expected` after generation** → the deterministic merge
  injected a `this.addCommand({...})` block without its trailing `);`. The
  `_extract_balanced_blocks` helper MUST consume the `);` after the closing brace.
- **Generation reports `existing_tests_passed: 0` even on the original suite** → the
  `PreTestRunner` jest-output metric regex doesn't match this project's jest summary
  format. That blocks self-correction; fix the parser (or run `make test-app` manually as
  the authority) rather than trusting the in-loop number.
- **Fast mode (`TEST_FAST_MODE=1`) MUST still run the `code_integrator` floor.** The e2e
  harness sets it (conftest.py) to skip the *npm-test* phase only. If `route_hitl` ever
  short-circuits `code_generation → output_result` again, the spec contract is not injected
  and a feature absent from the committed `main.ts` baseline (e.g. greetings) silently fails
  to appear — while uuid passes by accident (its modal already ships in the baseline). The
  greetings e2e is the regression guard for this: it proves the floor (not the baseline)
  injected a feature. Do NOT reintroduce any fast-mode routing that bypasses `code_integrator`.
- **`TEST_ULTRA_FAST_MODE` is no longer the orchestration shortcut.** The 233-line inline
  TS-writing block it gated was removed from `composable_workflows.py` (it bypassed the
  `CodeIntegratorAgent` sole-writer floor, B10/B11). The env var still lingers in two
  sub-workflow agents (`collaborative_generator`, `implementation_planner_agent`) but does NOT
  affect which TS writer runs — the deterministic floor is now the unconditional writer. Treat
  the var as legacy/no-op for the orchestration path; don't add new flow logic keyed on it in
  `composable_workflows.py`.
- **Request intake gate (front door) — turn inbound requests into OpenSpec changes before acting.**
  Before implementing/answering a new work request, convert it into an OpenSpec change of record
  (`make openspec-new NAME=<derived>` → `openspec new change`, per B15) + tasks, validate it, and
  **start the worktree flow** — according to the **per-channel trigger**:
  - **Hermes dashboard:** ALWAYS converts by default — no keyword required.
  - **Telegram:** converts / creates tasks / starts the flow ONLY IF the message contains the
    keyword `openspec` (case-insensitive). Messages without `openspec` are exempt.
  - **Hermes terminal CLI:** converts / creates tasks / starts the flow ONLY IF the command/text
    contains `openspec` (case-insensitive). Requests without `openspec` are exempt.
  After the change validates, the agent runs `make openspec-flow NAME=<name>` (or
  `scripts/openspec-change-flow.sh --name <name>`), which creates a dedicated worktree `feat/<name>`,
  scaffolds the change INSIDE it, generates + runs the loop gate inside it, archives on green,
  finalizes (squash in the worktree), and — with PUSH=1/`--push` — delivers by pushing `feat/<name>`
  as the PR. ALL artifacts stay in the worktree; the parent working tree is NEVER touched
  (B12 override: deliver = PR push, never a file copy). Corrections →
  `make openspec-redeliver NAME=<name>` (force-pushes to the SAME PR branch).
  Degenerate cases: re-use an in-flight change for the same intent (no duplicate dir); use
  `clarify` first if ambiguous.
  **Kanban-delivery path:** when a request arrives AS a Kanban task (assigned into a kanban
  workspace, agent scoped to that task), the Kanban wrapper is only the *delivery envelope* —
  the agent MUST still apply the per-channel trigger and scaffold the OpenSpec change via
  `make openspec-new` / `openspec new change`; do NOT limit itself to kanban tooling.  Mirrored in `AGENTS.md` (General Rules) and
  `docs/openspec-engineering-loop-harness.md` (B8). The reusable directive is the Hermes skill
  `request-to-openspec` (loaded at request entry).

## Durable agent behaviours (B1–B31) — MUST always hold, never regress

These are standing rules for the agent (also in `AGENTS.md`). They are enforced by
`make phase7-archive` and the persistent harness
`agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py`.

- **(B31) MAKE-THROUGH-DOCKER IS ALWAYS A BACKGROUND PROCESS — NEVER THE FOREGROUND SANDBOX.** Every Makefile target that invokes a container runtime (any `docker`, `nerdctl`, or `*compose*` via `$(call docker_run, …)`) MUST run through the Hermes `terminal(background=true)` channel on the REAL HOST that owns the docker/nerdctl daemon + live llama. The foreground sandbox (`/workspace`) has no container runtime and MUST NOT be used for these targets — mandatory for ANY such target, both the long-running ones (run-agentics, build-app, test-app, loop-harness, loop-e2e, deliver-change, phase7-archive, release-flow) and the short ones (loop-collect, loop-ts-floor, loop-unit, test-agents-unit, test-agents-integration, verify-agentics-after-run). The foreground sandbox prints `docker: command not found` — EXPECTED, not a blocker; the agent routes to the host and never reports "can't run from here".

- **(B1) Persistent E2E test per generated-TS change.** Every change that makes the pipeline
  generate TS code+tests MUST keep a runnable e2e test that reads THAT change's `tasks.md` and
  asserts the generated Modal is wired+integrated. The standing harness is
  `test_change_driven_ts_generation_e2e.py`. **NEVER delete it when archiving/done.** Archiving
  merges only the *spec*; the e2e file stays in the repo forever.
- **(B2) E2E reads the task file.** The e2e loads `openspec/changes/<CHANGE>/tasks.md` (+`spec.md`),
  confirms a "generate `<Feature>Modal` registered as a command" task exists, then asserts the
  generated `src/main.ts` contains that `obsidian.Modal` subclass wired via `this.addCommand(...)`.
  It validates against the change's own spec, never a hardcoded expectation.
- **(B3) E2E generates uniquely + is always runnable.** The harness runs the pipeline into an
  ISOLATED temp copy of the project (unique dir per run) — never touches the real `src/main.ts`.
  Runnable any time via `make test-agents-e2e` (`pytest -m e2e`); skips cleanly without a real
  llama. It re-generates the modal test code from the task every run to prove pipeline health.
  **Standing e2e gate (proof of concept) = THREE tests:**
  `test_ticket20_e2e_integration.py` + `test_ticket22_e2e_integration.py` (GitHub-issue
  seed-then-generate) + `test_greetings_e2e_integration.py` (LOCAL hand-authored change, the
  simple non-algorithmic proof). They MUST ALL pass after any Python slim/refactor. Greetings is
  the critical one: its modal is ABSENT from the committed `main.ts` baseline, so it proves the
  deterministic floor (not the baseline) injected the feature — uuid/ticket tests can pass by
  accident because the baseline already ships the uuid modal.
- **(B4) NEVER commit/push when generated task code already exists.** The pipeline and the e2e
  harness MUST NOT call `git commit` / `git push` / `git add` / `git merge`. `make run-agentics`
  and `make phase7-archive` only write/archive TS + spec files; they never touch git. Committing
  and pushing generated `main.ts`/`main.test.ts` is a deliberate, separate human action.
- **(B5) E2E restores TS files to the COMMITTED baseline.** After every run the harness restores
  the repo's real `src/main.ts` / `src/__tests__/main.test.ts` to **git HEAD (last committed)**
  state — NOT to whatever was on disk before. If generated task code already exists on disk but is
  uncommitted, the e2e rolls it back to the last commit; if committed, it stays. The e2e can never
  leave uncommitted generated TS behind and always runs against a known-good committed baseline.
- **(B6) If generated task code already exists, still restore to committed state.** When the
  change's task code was already generated (present on disk), the harness still RUNS and
  RE-GENERATES into the isolated temp dir to prove health, but writes nothing back to the repo and
  RESTORES the repo TS files to git HEAD afterward. Never commits/pushes, never keeps regenerated
  code in the repo.
- **(B7) Spec-driven deterministic assembly floor (OpenSpec spec wins).** When an OpenSpec
  change's `tasks.md`/`spec.md` pins an exact contract (id / command name / Modal class, parsed
  by `CodeIntegratorAgent._expected_contract_for_change`), the integrator does NOT trust the
  LLM's generated command body. `generate_updated_code_file` routes to
  `_assemble_contract_features`, which (string-only, idempotent):
  1. strips any non-contract `this.addCommand` + any existing/LLM Modal of that name from BOTH
     the existing file and the LLM output (so re-runs never duplicate),
  2. injects the AUTHORITATIVE contract command body (exact id/name, calls the spec generator),
  3. appends the spec Modal subclass + spec generator function ONLY if not already present.
  The contract is derived from the spec text (`uuid v7` → uuidv7 generator), never a hardcoded
  command string. This guarantees `build-app`/`test-app` pass even when the LLM under-delivers
  (run8 emitted a generic `generateRandomId()` with no Modal and failing tests). The
  `code_generator_agent` prompt is also tightened by injecting the same parsed contract as a
  "SPEC CONTRACT (honor EXACTLY)" bullet — prompt tightening comes from the spec file, not a
  literal string.
- **(B7.1) The deterministic floor runs in EVERY mode (incl. fast).** `route_hitl` used to skip
  straight to `output_result` when `TEST_FAST_MODE=1` (set by `tests/integration/conftest.py`),
  which bypassed `integration_testing` — the ONLY sub-graph that contains `code_integrator`. That
  meant the spec contract was never injected in fast mode and the raw LLM output landed in
  `main.ts` (a real B10/B11 violation, exposed by the greetings e2e whose modal is absent from the
  baseline). FIX: fast mode now routes `code_generation → code_integrator (floor) → output_result`,
  so the sole-writer ALWAYS runs; fast mode only skips the npm-test loop. Slow mode is unchanged
  (`code_generation → hitl/integration_testing → output_result`). Do NOT reintroduce a fast-mode
  shortcut that bypasses `code_integrator`.

- **(B8) Skill ↔ AGENTS.md bidirectional sync (never drift).** This skill and the repo's
  `AGENTS.md` are the SAME source of truth for the harness behaviour. Any change to a
  behaviour, constraint, command, or pitfall in ONE MUST be mirrored in the OTHER before the
  change is considered done. When editing this skill, re-read `AGENTS.md` first; when editing
  `AGENTS.md`, `skill_view openspec-loop-harness` first. Never leave the two files describing
  different behaviour. The full B8 sync set (enforced by `make check-docs-sync`, the FINAL loop
  stage) also includes `Makefile`, `docs/openspec-engineering-loop-harness.md`, and
  `scripts/run-loop-harness.sh` — all MUST agree on the 11-stage order (loop-collect → loop-ts-floor
  → loop-unit → loop-unit-real → loop-e2e → loop-integration → loop-build-app → loop-test-app →
  loop-release-tests → loop-secret-scan-tests → check-docs-sync), the `loop-ts-floor` guard, and the B1–B31 range; a drift
  there fails the loop.
- **(B9) Rootless nerdctl bind-mount permissions (READ + WRITE).** Execution is docker compose
  with **rootless nerdctl**, which remaps the container uid (1000) to the host **`other`** class.
  Every file/dir the container must READ (the whole repo, since compose mounts `..:/project`)
  MUST be world-readable + traversable: `chmod -R a+rX <repo>`. Every path the container must
  WRITE (`src/`, `backups/`, `openspec/.../specs`, `/project/results`, `.cache`) MUST be
  world-writable: `chmod -R a+rwX <write-targets>`. A missing `o+r`/`o+x` surfaces as
  `PermissionError: [Errno 13]` from the agent mid-run (e.g. reading a change `spec.md`, or
  writing `src/main.ts`). **ENFORCED BY THE MAKEFILE:** the `b9-perms` target applies both `chmod`
  commands and is a PREREQUISITE of `run-agentics` / `build-app` / `test-app`, so it runs
  automatically at the start of any such invocation — no manual step required (and never rely on
  group/owner perms alone). Run `make b9-perms` manually only if invoking docker compose outside
  the Makefile. World-readable on a private repo is acceptable.

- **(B10) NO hard-coded generated TS/test code in Python — only contract-steered.** When an
  OpenSpec change makes the agentic pipeline generate TypeScript (a command, Modal, generator
  method, or its tests), **the authoritative TS bodies MUST live ONLY in the change's `tasks.md` /
  `spec.md`** (a fenced ```` ```ts ```` block, split by `=== CONTRACT_* ===` / `=== TEST_CONTRACT_* ===`
  markers). `code_integrator_agent.py` (and ALL Python) MUST NOT contain any generated TS/test
  *bodies* as string literals — no `addCommand({...})`, no `class X extends obsidian.Modal {...}`,
  no `generateUuidV7() {...}`, no `describe(...)`/`it(...)` test bodies. Python only parses the spec
  markers via `_expected_contract_for_change`, performs the deterministic *merge* (anchors), and
  injects the spec's exact contract TS verbatim. The only acceptable spec-derived tokens in Python
  are *identifiers used for idempotency guards* (never the body text). **Verification:** `grep -nE
  "addCommand\(|extends obsidian\.Modal|describe\('|it\('|test\('" agents/agentics/src/*.py` must
  return ONLY comments / docstrings / idempotency-guard regexes, never TS body literals. This keeps
  the spec as the single source of truth: changing generated code = editing the OpenSpec change,
  not the Python.
- **(B11) On generated-TS failure: fix the SPEC, then restore, then re-run — never edit TS by hand.**
  If `make build-app` (`tsc`/`rollup`) or `make test-app` (jest) fails on the generated
  `src/main.ts` / `src/__tests__/main.test.ts`, the agent MUST NOT patch the TypeScript directly.
  The correct recovery sequence is EXACTLY:
    1. **Fix the OpenSpec change first** — edit `openspec/changes/<name>/tasks.md`
       (and/or `specs/<capability>/spec.md`): update the `## Contract` and `## Test Contract`
       fenced ```ts blocks, the `=== CONTRACT_* ===` / `=== TEST_CONTRACT_* ===` markers, or
       the acceptance criteria. The spec is the single source of truth; the fix lives THERE,
       not in the generated TS.
    2. **Restore** the generated `src/main.ts` and `src/__tests__/main.test.ts` to their
       timestamped `backups/` snapshot or the last committed baseline (so no broken generated
       code lingers and the next run starts clean).
    3. **Re-run** `make run-agentics` to regenerate from the corrected spec, then
      `make build-app` + `make test-app` until green.
  **Bounded self-correct loop (≈5 e2e attempts):** repeat the fix-spec → restore → re-run
  sequence for up to ~5 full e2e runs (`make run-agentics` with that spec file). Each failed
  attempt MUST first try a **different adjustment to the spec/contract file** (tasks.md
  `## Contract` / `## Test Contract` blocks or markers) — never a hand-edit of the generated TS,
  and the restore (step 2) MUST happen before every re-run so no broken generated code carries
  over. Only after ~5 spec-driven attempts still fail may the agent fall back to editing the
  **Python agentic code** (the integrator / contract parser / self-correct loop) as a LAST
  resort; even then, the generated TS is never patched by hand.
  The Python pipeline (`CodeIntegratorAgent.integrate_test_contract`,
  `_expected_contract_for_change`) only reads the spec contract and merges it deterministically —
  it must never author TS bodies. Hand-editing generated TS is forbidden because it bypasses the
  deterministic merge floor and desyncs the spec from the code.
- **(B12) Delivery gap — verified worktree TS MUST reach the target branch as the PR.** The pipeline
  generates + verifies TS **inside a git worktree** (`worktrees/<name>`, branch `feat/<name>`).
  The harness MUST NOT stop there: a feature green only in the worktree that never lands on its
  target branch is a failed delivery. The agent delivers by **pushing the worktree branch as the PR**
  (`git push origin feat/<name>`, or `make openspec-flow NAME=<name> PUSH=1`) — it MUST NOT copy
  generated TS back into the parent working tree (that would re-introduce pollution; ALL artifacts
  stay in the worktree by design — see `openspec-change-worktree-flow`). Corrections redeliver via
  `make openspec-redeliver NAME=<name>` (`git push --force-with-lease` to the SAME PR branch only;
  never `main`). Never declare a change "done" while its worktree branch has not been delivered.
  (Earlier wording told the agent to `make deliver-change` — a file copy onto the current branch —
  which conflicts with the worktree-confinement invariant; this override supersedes it.)
- **(B13) Python *floor* defects are fixed directly, not via spec round-trips.** B11's spec-first
  rule applies when the GENERATED TS/test is wrong. If the defect is in the *deterministic floor*
  itself (e.g. the integrator skips injecting the spec contract when the LLM already emitted a same-
  named block, causing non-deterministic output), fix the Python (`CodeIntegratorAgent`) directly —
  that is the correct, spec-steered fix, not a hand-edit of generated TS. The contract TS body still
  comes from the spec's `## Contract` markers; only the *merge logic* is corrected.
- **(B14) Commit/push gating for *new* code (human-only, behaviour-scoped).** Standing user rule:
  **code is committed ONLY if it is NEW, and pushed ONLY if that NEW code is part of a behaviour.**
    1. The agent NEVER runs `git commit` / `git push` itself (extends B4). These are deliberate,
       separate **human** actions.
    2. Generated TS/`main.test.ts` is the implementation of an already-approved OpenSpec change, not
       "new behaviour" in the gating sense — committed/pushed only on the human's explicit go-ahead.
    3. Floor/integrator fixes to `code_integrator_agent.py` ARE new behaviour-logic. They MAY be
       committed (and pushed only when that new logic forms part of a committed behaviour) **but
       ONLY once all hold**: `make build-app` exits 0, `make test-app` exits 0, the passing-test
       count is **greater than the previous run**, and all OpenSpec checks pass (`openspec validate
       <change>` + `openspec status --change <change>` clean). The agent proposes; the human triggers.
    4. Rule of thumb: **commit only if new AND build-app works AND test-app works AND tests pass >
       last run AND all OpenSpec checks passed; push only if that new commit is the behaviour being
       landing.** Never squash/rebase/force-push (user hard requirement).
    - **(B16) Task-completion discipline — tick as you verify, never leave open tasks, archive gate
    fails closed.** The agent MUST tick each `tasks.md` checkbox (`- [ ]` → `- [x]`) the MOMENT the
    underlying work is actually finished AND verified — never complete work in code while leaving the
    checklist unticked (that desync caused 9 stale change dirs). The agent MUST keep grinding the
    loop-engineering backlog (`openspec/changes/*`) until every active change is fully ticked and
    archived, and MUST NOT stop mid-backlog unless the user explicitly says so. Mechanical enforcement:
    `make phase7-archive CHANGE=<name>` runs `openspec_loader.assert_no_open_tasks` BEFORE
    `openspec archive` and **refuses (non-zero exit, no spec merge) if any `- [ ]` task remains**;
    `make loop-tasks` lists open/done counts per change so the backlog is never invisible. A change is
    "done" only when all tasks are ticked AND verified AND archived (spec merge only — B4/B14 still
    forbid extra git commit/push). Code-fenced `- [ ]` lines in `tasks.md` are NOT counted as open.
    **Convention (closes the self-referential loophole): the final task in any `tasks.md` MUST be a
    *verification* tickable the moment the work is done — e.g. "openspec validate <name> passes" or
    "fast loop-integration subset green" — NEVER "run make phase7-archive". A task whose body is the
    archive command can never be ticked before the archive (chicken-and-egg), which defeated the
    tick-when-verified rule. Tick every task (incl. the final verification) BEFORE invoking archive;
    the archive command is the *last action*, not a task to be ticked.

    - **(B17) Integration suite is a mandatory loop phase; no dead tests; live tests skip cleanly.** The
      agentic integration suite (`agents/agentics/tests/integration/*`) is a FIRST-CLASS loop gate.
      `make loop-harness` runs TEN stages in this exact order: a collection guard (gate 0), a
      strict TS test/command floor (gate 0.5), followed by six gates (1–6): `loop-collect` (hermetic
      collection guard — fail fast on dangling imports, rule 4 below) → `loop-ts-floor` (STRICT TS
      test/command floor — FAIL if the current branch's `describe`/leaf `it`/`test`/jest-collected/
      `addCommand` counts drop below `origin/main`; the silent feature/test-removal guard) → `loop-unit`
      (mocked, hermetic) → `loop-unit-real` (REAL agent unit tests on live llama, no mocks) → `loop-e2e`
      (the 3 standing B1/B3 e2e gates) → `loop-integration` (broad agentic integration suite) →
      `loop-build-app` → `loop-test-app`. Each stage fails the whole run (no silent green). Rules for the
      integration tests:
        1. **No dead tests.** Delete strict duplicates / files superseded by a canonical per-agent file
           (e.g. `test_jest_execution_integration_fixed.py` / `test_jest_execution_minimal.py` duplicate
           `test_jest_execution_integration.py` → removed). The `integration-test-duplicate-audit` change
           confirmed the remaining suite has no strict duplicates — the only structural twin
           (`test_ticket20_e2e` ↔ `test_ticket22_e2e`) is a B3-mandatory distinct-capability gate, kept.
        1b. **`loop-integration` runs the FAST subset only.** It invokes `test-agents-integration` with
           `INTEGRATION_TEST_FILTER="-m 'integration and not e2e and not slow'"`, EXCLUDING (a) the 4 e2e
           files (covered by `loop-e2e` stage 3) and (b) `@pytest.mark.slow` tests — the ~70 heavy
           full-pipeline (`process_issue`) tests that each fire the real multi-agent LLM pipeline and made
           the old full run ~53 min. Slow tests are NOT deleted; `make test-agents-integration` (full suite,
           incl. e2e + slow) is the deliberate deep-verify target. Keeps `loop-integration` ~6 min.
           (Marker in `pytest.ini`; heavy files tagged in `setup-loop-harness-openspec`.)
        2. **Live tests skip cleanly.** Tests needing a live llama endpoint (`LLAMA_HOST`) MUST
           `skipif` so they SKIP (not error) when absent — `make loop-integration` exits 0 with a skip
           count, creds-less. **GitHub public-repository reads are token-less**, so `GITHUB_TOKEN` is
           NOT a skip condition: tests that only read public issues must run without a token and skip
           only on `LLAMA_HOST` (per the user correction during `integration-tests-lifecycle`; applied
           to `test_agentics_app_integration.py` + `test_configuration_integration.py`).
        3. **Categorization is provable.** Keep an inventory (hermetic / live-llama / live-GitHub / dead)
           in the active change's `tasks.md` so "integration tests work + are updated (not just dead)" is
           demonstrable. (Added via the `integration-tests-lifecycle` OpenSpec change.)
        4. **Collection guard (fail-fast on dangling imports).** `make test-agents-collect` runs
          `pytest --collect-only` for BOTH `tests/unit/` and `tests/integration/` and is non-zero on any
          collection error. It is wired into `.github/workflows/test-on-commit.yml` so a slim-refactor
          that orphans a symbol (deletes a module a test still imports) FAILS CI instead of reporting a
          cached "green". Durable guard from `audit-mcp-slim-refactor-integrity` — never remove it.
        5. **A green gate MUST NOT rely on FALSE skips.** A skip is legitimate ONLY when its dependency
           is genuinely absent. A skip whose dependency IS present is a FALSE skip = GATE DEFECT. After
           every loop run, inspect the skip list; confirm each skip reason is true; fix any false skip
           (root cause is usually wrong root resolution or stale skip reason), never leave it. The
           integration container mounts the repo at BOTH `/app` and `/project`, but `/app/src` is
           shadowed by the agentics Python bind-mount, so `_repo_root()` MUST prefer the unshadowed
           `/project` (has `src/main.ts`). A "No src/main.ts in repo" skip when `/project/src/main.ts`
           exists is a defect, not a pass.
    - **(B18) Run the agents' REAL unit tests, not only the mocked ones.** The loop MUST
      execute BOTH the hermetic mocked unit run (`loop-unit` → `test-agents-unit-mock`) AND the
      real, non-mocked agent unit run (`loop-unit-real` → `test-agents-unit`, live llama) as gates
      1 and 2 of `make loop-harness`. Reporting "agent tests green" after ONLY the mocked run is
      INCOMPLETE — `loop-unit-real` proves the deterministic floor + agent units actually work
      against the live LLM (the unit under test is never mocked; only the llama/HTTP boundary may
      be). `make test-agents-unit` MUST be run when llama is reachable and its result reported
      alongside — not instead of — the mocked run. If llama is unreachable, `loop-unit-real` SKIPS
      (it must not error), but the agent MUST note that the real unit gate did not execute rather
      than silently treating the mocked run as the whole story. (Closes the gap where the agentic
      suite was reported green from the mocked run alone. Tasks tracked in `agentic-tests-real-logic`.)
    - **(B19) Archived change dirs carry a `YYYY-MM-DD-` prefix — resolvers/tests MUST handle it.** `openspec archive` moves `openspec/changes/<name>` → `openspec/changes/archive/<YYYY-MM-DD>-<name>`. `openspec_loader.find_change_dir`, `CodeIntegratorAgent._expected_contract_for_change`, `run_pipeline_isolated` (e2e helper), and the contract/regression unit tests MUST also match the date-prefixed archived variant (`archive/*-<name>`), else those tests become dead tests (B17 violation). Repo root: in the unit/e2e containers the real repo is at `/project` (sibling of `/app`), so a naive `../..` walk-up or `git rev-parse` from `/app` FAILS — probe for a dir containing `openspec/changes`. The e2e/integration gates run the REAL pipeline against a live llama (`integration-test-agents` sets `LLAMA_HOST=http://127.0.0.1:11434` — rootless-nerdctl
 host-networked containers, so `host.docker.internal` does NOT resolve; the coordinate
 `127.0.0.1:11434` reaches the live llama on the docker host), so they must RUN (not skip) — fix
 root resolution, never add an LLAMA skip guard. (Closed the gap where `test_greetings_contract_unit.py` + `test_slim_refactor_invariants_unit.py` failed post-archive, and where `test_ticket20/ticket22/greetings` e2e errored on `FileNotFoundError: 'openspec'` due to `/app` root resolution.)
    - **(B20) NEVER declare a change "done" without running the loop gate first — hard pre-flight.** Before claiming any OpenSpec change complete (or "harness green/aligned/fixed"), run the gate and report real output:
      1. **Preferred:** `bash scripts/run-loop-harness.sh` (wrapper over `make loop-harness`) — all stages: `loop-collect` → `loop-ts-floor` → `loop-unit` → `loop-unit-real` → `loop-e2e` → `loop-integration` → `loop-build-app` → `loop-test-app` → `loop-release-tests` → `loop-secret-scan-tests` → `check-docs-sync`. Also `make loop-trigger`.
      2. **If full `make loop-harness` can't finish** (live llama absent for `loop-e2e`/`loop-unit-real`, or npm build times out), STILL run the hermetic gates `make loop-collect` + `make loop-ts-floor` + `make loop-unit` (no external dep) — they MUST be green before any "done".
      3. **Report honestly:** actual per-stage PASS/SKIP/FAIL with the failing stage named. Never say "done/green" if `loop-unit`/`loop-collect` is red; fix the root cause and re-run. Rationale: the agent previously finished work (incl. AGENTS.md/skill edits) WITHOUT running the gate, leaving `make loop-unit` red. B20 makes the gate mandatory so regressions are caught before "done". (B4/B14: no git commit/push from the gate.)
    - **(B21) HITL is OPT-IN and loop-excluded — never a blocking prompt in automation.** `HITLNode`
      (`src/hitl_node.py`) only prompts a human (`input()`) when ALL hold: validation score `< 80`, not in
      CI, `HITL_ENABLED=1`, `INTERACTIVE_HITL=1`, and `sys.stdin.isatty()` true. In loop/CI/`make run-agentics`
      automated runs none hold, so the node returns `state` UNCHANGED (no-op pass-through, no `human_feedback`
      key). HITL is a deliberate human-at-terminal feature, NOT a loop gate. Automated HITL tests MUST assert
      the **pass-through** (state unchanged, no `human_feedback`), never the interactive-only key (flaky in
      the loop). The two-flag gate stops a leaked `HITL_ENABLED` from ever blocking the loop on `input()`.
      (Captured in `hitl-optin-loop-excluded` change + `hitl-optin` spec. B8: mirror in AGENTS.md + skill + spec.)
    - **(B22) Release automation is a POST-GREEN loop-engineering stage, never part of the 7-stage
      verification gate, and NO push.** The Makefile prepares a release LOCALLY; the actual GitHub
      release is cut by CI (`.github/workflows/release.yml`, on merge to `main`). Local commands:
        - **`make bump-local`** — LOCAL staging: `check-released` → `bump-version` (Obsidian way:
          `package.json`+`manifest.json`+`versions.json`) → `tag-release` (LOCAL tag only). NO
          squash/changelog/release-notes/push. Advance the version locally (e.g. `make bump-local PART=patch`).
        - **`make squash-commits`** — squash to one TYPED Conventional commit.
        - **`make changelog`** — regenerate sectioned `CHANGELOG.md`.
        - **`make release-notes`** — refresh README release-notes block.
        - **`make release-prep`** — local publish-prep wrapper: `check-released` → `bump-version` →
          `squash-commits` → `changelog` → `release-notes` → `tag-release` (LOCAL tag only). CI does
          the real GitHub release on merge to main. NO push (B14).
        - **`make loop-release`** — loop-facing variant: same steps, NO-OP if no generated TS changed
          vs HEAD, runs `check-released` first.
      `check-released` FAILS if the CURRENT `package.json` version is ALREADY released on GitHub
      (remote tag `<version>` OR `v<version>`, tolerant) OR does NOT advance past the latest released
      version (no semver gap) — bump only when not-yet-released AND a real forward gap exists. FAILS-CLOSED
      if `gh`/network unavailable. The squashed commit's Conventional `type(scope):` prefix is the
      SINGLE SOURCE OF TRUTH: `squash-commits` FORCES a valid `type(scope):` first line, FAILS-CLOSED if
      untyped, driving BOTH the changelog section (feat→✨, fix→🐞, docs→📝, refactor→🔧, chore→🛠️) AND the
      bump semantics. Pushing commit+tag is a deliberate human action that triggers CI to publish.
      (NOTE: the pre-existing `release` Makefile target is the CI build-zip step — left intact for
      `release.yml`; do NOT reuse it for local prep.) (Captured in `release-automation` spec. B8: mirror.)
    - **(B23) NEVER let a pipeline/release fix die in the working tree — COMMIT fix-work before any
      reset-capable verification.** A `git checkout -- <files>` / `git reset --hard` DESTROYS uncommitted
      work. The 2026-07-15 incident: changelog/bump fixes were uncommitted, then a test's
      `git reset --hard origin/main` wiped them. RULES: (1) commit the moment a fix is written (separate
      commit, not the squash-commits flow); (2) verify against committed state; (3) test cleanup removes
      only throwaway artifacts (`git reset --soft HEAD~1`, `git tag -d <temp>`), never `reset --hard
      origin/main`; (4) no multi-file fix left uncommitted across a tool-call boundary. Permitted under
      B14 (fix-work, local commit, no push unless human triggers CI). B8: mirror in AGENTS.md.
       **loop-finish (green-gated finalisation):** when the loop gate is GREEN (B20: `make loop-harness`
      passes) and the backlog is clear (every active change open=0), run `make loop-finish`. It chains:
      `assert-backlog-clear` (FAILS CLOSED on any open task) → `archive-all-complete` (archives every
      active change via `phase7-archive`, B16 gate) → `squash-commits` (one TYPED commit) → `changelog`
      → `bump-from-changelog` → `changelog-format`. NEVER push (B4/B14). Never hand-run the steps
      piecemeal, never run on a red gate or with open tasks.
    - **(B24) NEVER `git reset --hard` / `git checkout --` / delete commits on the PARENT branch — work
      ONLY inside an isolated WORKTREE (or throwaway `wt/<name>` branch) and SYNC BACK when green.** The
      agent is forbidden from destroying history/uncommitted work on the active branch. Any lossy op
      (`reset --hard`, `reset --mixed` past authored commits, `checkout --` on source, `branch -D` of a
      fix-holding branch, `clean -fd`) MUST run in a sandbox that cannot touch the parent:
      (1) `git worktree add ../worktrees/<name> -b wt/<name>` and do ALL risky work there (`reset`/
      `checkout` inside only affects the worktree); merge back + `git worktree remove` when green;
      (2) if a worktree is impractical, use a throwaway `wt/<name>` branch (lightweight backup, not the
      forbidden `reset --hard`); (3) parent is read-mostly — agent may `commit`/`merge`/`cherry-pick` but
      MUST NOT `reset`/`checkout` it past authored work nor `branch -D` un-synced fix-work; a parent reset
      requires the human; (4) compose `make` targets may fail on mount-root resolution inside a worktree
      (B19) — run the underlying scripts directly there to validate logic. B8: mirror in AGENTS.md.
    - **(B25) NEVER squash/merge-squash commits on the current branch without EXPLICIT human approval
      in that branch.** The agent is forbidden from running `make squash-commits`, `git rebase -i` with
      squash/fixup, or `git reset --soft` + commit to collapse history, unless the human explicitly said
      to. Hard gate, separate from B14 (no-push) and B24 (no parent reset): the human owns the commit
      graph. The agent MAY commit (B23) and merge/cherry-pick, but must NOT rewrite/squash existing
      history. If history is messy (leaked throwaway commits), FLAG it for the human and ask — do not
      decide unilaterally. `make squash-commits` is human-triggered only. B8: mirror in AGENTS.md.
    - **(B26) AGENT MAY COMMIT AND PUSH ITS OWN CHANGES on a non-main branch when the LOOP GATE IS
      GREEN and the PRE-COMMIT HOOK PASSES.** Permitted to `git commit` (and `git merge`/`git
      cherry-pick`, and `git push` to its OWN feature/PR branch) its OWN work-in-progress so the
      remote stays synced. Bounded by: (1) branch guard — current branch MUST NOT be `main`/
      `origin/main`/protected; (2) hook guard — `git-hooks/pre-commit` (gitleaks + trailing-
      whitespace) MUST pass; the agent commits only via the normal `git commit` path, NEVER
      `--no-verify`; (3) loop-gate guard — push ONLY after the OpenSpec/loop gate is GREEN for the
      change (build-app=0 + test-app pass, and/or check-docs-sync PASS for doc-only changes), never
      push red work; (4) still forbidden (human-only): `git push` to main (B14), `make squash-commits`,
      `git rebase -i` squash/fixup, `git reset --soft` collapse (B25). Adds commit/merge/**push-to-own-
      branch** latitude on feature branches; does NOT lift no-push-to-main/no-squash/no-force. B8:
      mirror in AGENTS.md + harness doc.
    - **(B27) AGENT WORKS IN A LOCAL WORKTREE SANDBOX, THEN AUTO-DELIVERS THE PR ON COMPLETION — EVERY
      TIME.** For every OpenSpec change the agent's working mode is an isolated **local** git worktree
      sandbox (`worktrees/<name>` on a throwaway branch `wt/<name>`): it does its implementation,
      generation, loop gate, and archive THERE, and it creates NO `feat/<name>` branch and pushes
      NOTHING during the work — the parent working tree stays untouched. **As soon as the change is
      COMPLETE** (all `tasks.md` checkboxes ticked AND the loop gate is GREEN AND the pre-commit hook
      passes — B26's guards), the agent **AUTOMATICALLY** promotes `wt/<name>` → `feat/<name>`, pushes
      `origin feat/<name>`, and opens the PR — **every time, by default, with no second "make the PR"
      prompt.** Green-lighting a change IS the delivery authorization; completion triggers delivery.
      Bounded + parallel-safe: (1) **Sandbox during work:** `git worktree add ../worktrees/<name> -b
      wt/<name>`; all change work lives there; the parent working tree is never touched; no remote
      branch exists yet. (2) **Auto-deliver on completion:** once `tasks.md` is fully ticked AND
      `openspec validate <name>` + the loop gate pass AND `git-hooks/pre-commit` is green, the agent
      promotes `wt/<name>` → `feat/<name>`, pushes `origin feat/<name>`, and opens the PR without
      further prompting. (3) **Parallel-safe:** each change uses a UNIQUE worktree (`worktrees/<name>`),
      a UNIQUE branch (`wt/<name>` during work, `feat/<name>` on delivery), and a UNIQUE compose
      project name (`COMPOSE_PROJECT_NAME=otu-<name>`). Many agents can each iterate in their own
      sandbox and deliver their own distinct PR branch concurrently with no collision. (4) **This is the
      default flow:** `make openspec-flow NAME=<name>` (and `wt-create`, `openspec-change-flow.sh`)
      create the local `wt/<name>` sandbox, run the gate, and — on green — automatically promote + push
      + open the `feat/<name>` PR. `PUSH=1`/`--push` is retained as an explicit alias but is now the
      default behaviour, not an opt-in. B8: mirror in AGENTS.md + harness doc.
    - **(B28) PR-REVIEW STABILITY — NO SQUASH AFTER REVIEWER ENGAGEMENT; gh-DRIVEN COMMENT RESOLUTION.**
      Two rules that protect a human reviewer's incremental diff once a branch is live as a PR:
      (1) **B28a No squash on an engaged PR:** `squash-commits`, `loop-finish`, and `openspec-redeliver`
      MUST refuse (fail closed) when the current branch is the head of a PR with reviewer engagement —
      `gh pr view` reporting `comments > 0` OR `reviews > 0` OR a non-dismissed review thread. After
      engagement all corrections land as **NORMAL (non-squashed) Conventional commits** on the PR branch,
      pushed normally (no `--force`, no squash). Fail-open on `gh` absence (proceeds if `gh`/token
      unavailable; only blocks when `gh` confirms an engaged PR).
      (2) **B28b gh-driven PR resolution:** when the prompt says "go to the PR for `<branch>`" (or
      "resolve the PR comments" / "address the review"), run `make pr-resolve BRANCH=<branch>` (→
      `scripts/pr_resolve.sh`), which uses `gh` to fetch + print the PR's comments and review threads;
      the agent follows each **strictly**, fixes the code, commits as a NORMAL (non-squashed)
      Conventional commit, and pushes **normally** (never `--force`, never squash). The script commits/
      pushes nothing itself; `pr-resolve` and `squash-commits` are mutually exclusive on a reviewed
      branch. B8: mirror in AGENTS.md + harness doc.
    - **(B29) TWO-WAY PR INTERACTION — COMMENT THE FIX + COMMIT ON GREEN GATE.** Extends B28 with
      agent→participant signalling so a human reviewer can resolve threads:
      (1) **B29a Comment the fix:** after applying a code fix for a PR comment/review thread, post a
      PR comment (`make pr-comment BRANCH=<b> BODY=<text>` → `scripts/pr_comment.sh` → `gh pr comment`)
      summarizing the fix and linking the fixing sha (e.g. `Fixed in <sha>: <summary> — resolves
      <comment>`). Gives the participant a visible, resolvable signal.
      (2) **B29b Commit on green gate (no squash):** when resolving an open PR's comments, run
      `make loop-harness` (B20 pre-flight); when GREEN, commit the fix(es) as NORMAL (non-squashed)
      Conventional commits and push the PR branch normally (no `--force`, no squash). B28a still
      forbids squashing an engaged PR.
    - **(B30) NEVER REVERT — SQUASH ONLY PRE-PR.** Standing git-history rule (user correction):
      (1) **B30a No revert ever:** never `git revert`/`reset`/`rebase -i` on ANY branch (esp. a PR
      branch); corrections are forward NORMAL commits only. (2) **B30b Squash pre-PR only:** the
      Makefile `squash-commits` guard refuses (fail-closed) when `gh pr view` shows an open PR for the
      branch OR the branch tracks a pushed remote — once pushed, squash would rewrite public history
      (extends B28a from "engaged" to "any open/pushed PR"). (3) **B30c Red gate → forward fix:**
      a RED `loop-harness` after push is fixed with a new NORMAL commit (+B29a PR comment), never a
      revert/rewrite. B8 sync in AGENTS.md + harness doc.
    - **(B30d) Explicit override flag:** `make squash-commits ALLOW_SQUASH=1` lets the human
      deliberately bypass the B28a/B30b guard (e.g. an agreed pre-merge cleanup). OFF by default;
      always prints a loud WARNING that history is rewritten on explicit request. Does NOT bypass
      B30a (no revert). Use only when the user explicitly asks. B8 sync in AGENTS.md + harness doc.
    - **(B29c) Never self-resolve/approve:** the agent posts the fix comment and leaves the thread
      for the human participant; it does NOT resolve the reviewer's thread or approve its own PR.
      B8: mirror in AGENTS.md + harness doc.
    - **(B32) `loop-final` — REVIEW-APPROVED SQUASH + CHANGELOG + FORCE-PUSH.** The ONE sanctioned
      exit from B28a/B30b. Default (no approval) STANDS: agent never squashes/force-pushes an open PR
      on its own. Once a human REVIEWS + APPROVES the PR (phrase like "PR looks great" / "looks good"
      / "approved to finalize"), the agent runs `make loop-final BRANCH=<feat/...> APPROVED=1`, which:
      (1) **B32a** fails closed unless `APPROVED=1` (agent sets it ONLY on a human approval phrase,
      never in automation); (2) **B32b** runs a FRESH `make loop-harness` FIRST and aborts if not
      green — history is never rewritten on a red gate (B30c still holds); (3) **B32c** on green,
      `squash-commits ALLOW_SQUASH=1` (B30d sanctioned override) → `changelog` → `bump-from-changelog`
      → `changelog-format`, regenerating the CHANGELOG from the single squashed typed commit;
      (4) **B32d** `git push --force-with-lease` the feature branch ONLY (refuses main/origin/main);
      (5) **B32e** B30a stays absolute — no `git revert`, ever. Rationale: reviewer needs a stable
      diff DURING review (B28a/B30b); once approved, owner wants tidy single-commit history for merge.
      (B31 = concurrent make-always-background / PR #58; this is B32.) B8: mirror in AGENTS.md +
      harness doc.
    ## Plan-B merge refactor (integrator-merge-refactor)

- **Imports:** inject new `import` lines at the top (after the last existing top-level import).
- **`onload`:** the single `this.addCommand({...});` block for the spec contract is injected
  inside `onload()` (matched via `def onload(` / first `addCommand(` anchor), never appended at
  file end.
- **Closing brace:** the spec Modal class + spec generator function are injected just BEFORE the
  file's final `}` (the `export default class` closing brace), so they become top-level module
  members, not orphans.
- **`_extract_balanced_blocks` is line-aware.** It captures from the START OF THE SOURCE LINE
  (incl. a leading `export `) through the matching close brace, then `_assemble_contract_features`
  strips that `export ` before re-injecting — so generated `export class <Feature>Modal` survives
  the merge (a prior bug overwrote the line-start capture with a `class`-only slice and dropped
  `export`, producing orphans that broke `tsc`).
- **No omission:** merged output length MUST be `>=` input length; an assertion guards this
  (see `tests/unit/test_integrator_merge_unit.py`).
- **pytest pin:** `requirements.in` pins `pytest-asyncio>=1.4.0` (pytest 9 needs >=1.4.0; 1.3.0
  crashes with `'Package' object has no attribute 'obj'`). Regenerate after any `.in` change.
