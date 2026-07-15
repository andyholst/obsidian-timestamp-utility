# Project Instructions for Hermes Agent (OpenSpec Workflow)

You are working in a spec-driven project using **OpenSpec** (CLI `@fission-ai/openspec`).
The source of truth for any change is an OpenSpec **change** under `openspec/changes/<name>/`
containing `proposal.md`, `tasks.md`, optional `design.md`, and `specs/<capability>/spec.md`.
The Python agentic pipeline (`agents/agentics`) **reads these local files** (not GitHub) to
generate and test TypeScript — driven through the Makefile. All execution runs via Docker
compose (no Dagger, no MCP).

This file's behavior is the authoritative expansion of
`docs/openspec-engineering-loop-harness.md`. Follow it phase-by-phase.

---

## Fundamentals — what harness engineering and loop engineering are

This entire repo is a concrete implementation of two disciplines. Understand them before the
phases below (full write-up: `docs/openspec-engineering-loop-harness.md` §0; mirrored in
`hermes/skills/openspec-loop-harness.md`).

**The core problem.** An LLM is a *non-deterministic generator*: it drifts (near-misses like
`insert-random-id` instead of the spec's `insert-uuid-v7`), omits existing logic when it
regenerates a file, hallucinates imports/APIs/tests, and never produces the same output twice.
You cannot ship software by trusting raw LLM output directly. Harness + loop engineering are the
two complementary answers — one *constrains* the generator, the other *corrects* it.

**Harness engineering = constrain the generator into a verifiable shape.** A harness is the
deterministic scaffolding (a machinist's "jig") around the LLM that forces its output into a
known-good, checkable form. Its pillars here: a **single source of truth** (the OpenSpec change's
`## Contract` / `## Test Contract` — generated TS never lives in Python, B10); the **LLM never
holds the pen** (the `CodeIntegratorAgent` deterministic string-merge floor is the *sole* writer
of `src/main.ts`; the LLM only proposes raw candidate text, B7/B11); **bounded, checkable output**
(idempotent contract injection, the omission guard, git-HEAD restore B5/B6); and **one
reproducible execution path** (docker compose only, pinned `requirements.in`, the B9 perms floor).
It makes an unreliable generator produce reliable artifacts.

**Loop engineering = correct the generator across attempts until an objective gate passes.** A
closed feedback loop with four parts: (1) **generate** — run the pipeline; (2) **verify** against
an objective gate that defines "done" (`make build-app` exit 0 + `make test-app` pass + a walk of
every spec requirement/scenario); (3) **diagnose & correct by fixing the SOURCE OF TRUTH, not the
symptom** — edit the OpenSpec spec/contract, restore the generated files to a clean baseline, and
re-run; NEVER hand-edit generated TS (B11), and each pass must try a *different* correction; and
(4) **terminate** — a bounded ~5 attempts with a clear escalation (fix the Python floor as a last
resort, B13). The durable behaviours B1–B18 are the loop's "laws of physics" — invariants that
never regress on any pass (permanent e2e B1–B6, no-commit/no-push gate B4/B14, delivery step B12).

**How they fit:** the harness is the **floor** (nothing worse than the contract can ever be
written); the loop is the **ratchet** (each pass only moves toward green, and the invariants never
slip back). Everything below is the concrete machinery that implements both.

---

## Phase 0 — Project structure (already scaffolded)

`openspec/` (specs + changes), `hermes/skills/`, `hermes/prompts/`, `agent-wiki/`,
`worktrees/`, and this `AGENTS.md` already exist. Container definitions live in `containers/`,
one directory per container (`containers/npm/`, `containers/agents/`, `containers/pip/`, …),
each with its own `Dockerfile`, referenced by `docker-compose-files/*.yaml`.

---

## Phase 1 — Standard OpenSpec Workflow (follow automatically)

When a change is active in `openspec/changes/`, run these phases in order.

### Phase 2 — Propose (create the change with the CLI)
Create the change directory with the **real `openspec` CLI** (never hand-write it — durable
behaviour B15). The reproducible harness wraps exactly this CLI step and then seeds the
conventional files (`proposal.md` / `tasks.md` / `specs/<capability>/spec.md`) from a template:
```bash
make openspec-new NAME=<kebab-name> [CAPABILITY=<cap>] [DESC="..."] [GOAL="..."]
# equivalent manual CLI step (what the harness runs under the hood):
openspec new change <kebab-name>        # creates openspec/changes/<kebab-name>/
```
`make openspec-new` invokes `openspec new change <name>`, seeds the delta-format files, and runs
`openspec validate <name>` so the change is green before you implement. `NAME` is required;
`CAPABILITY` defaults to `NAME`. It refuses to overwrite an existing change dir.
Write `proposal.md` (Why / What Changes / Capabilities / Impact) and, for each new capability,
`specs/<capability>/spec.md` in the **delta format** the CLI validates:
```markdown
## ADDED Requirements
### Requirement: <name>
The system MUST <text>.
#### Scenario: <name>
- **WHEN** <condition>
- **THEN** <outcome>
```
Optionally add `design.md`. Use `openspec instructions proposal --change <name>` /
`openspec instructions tasks --change <name>` for the exact templates.

### Phase 3 — Generate the tasks from the spec
Write `tasks.md` as a tracked checklist (`- [ ] X.Y ...`). These tasks are **the executable
plan the agentic code reads and runs** — keep them concrete and verifiable (build / run / assert).
Each task maps to a step the agentic pipeline or you will execute.

### Phase 4 — Validate before implementing
```bash
openspec validate <name>                # proposal + specs (delta) + tasks must parse
openspec status  --change <name>        # artifact completion
```
Do NOT implement until `openspec validate` passes.

### Phase 5 — Implement safely in a git worktree
```bash
git worktree add ../worktrees/<name> -b feat/<name>
cd ../worktrees/<name>
```
- Work ONLY on the tasks in this change's `tasks.md`. No scope creep.
- **BACK UP BEFORE GENERATING.** Before running the agentic pipeline, `make run-agentics`
  automatically timestamp-backups `src/main.ts` and `src/__tests__/main.test.ts` into
  `backups/` (e.g. `main.ts.20260713-101530.bak`). Never skip this — it is the safety net.
- For features generated by the agentic pipeline, run it FROM THE WORKTREE:
  ```bash
  make run-agentics CHANGE=<name>        # backs up main.ts/main.test.ts (timestamped), then
                                           # reads openspec/changes/<name> locally (no GitHub, no MCP)
  ```
  The pipeline ingests `proposal.md` + `tasks.md` + `specs/**` (via `agents/agentics/src/openspec_loader.py`)
  and regenerates `src/main.ts` / `src/__tests__/main.test.ts` under `PROJECT_ROOT`.
  > The previous `main.ts` / `main.test.ts` are preserved (worktree is a separate checkout), so the
  > old TS code and tests always remain until you deliberately merge the worktree.
- **GITHUB ISSUE AS THE SOURCE (seed-then-generate).** When the change is driven by a GitHub
  issue rather than a pre-existing local change, the agentic code does NOT hand-write a change
  directory — it reuses the **same OpenSpec CLI flow** at runtime:
  1. `fetch_issue_agent.py` fetches the issue once (live GitHub, needs `GITHUB_TOKEN`).
  2. It calls `openspec_loader.create_change_from_issue(url, title, body)` — which **shells out to
     `openspec new change ticket<N>`** to scaffold the change directory (the exact CLI step a human
     runs), then writes `proposal.md` / `specs/<cap>/spec.md` / `tasks.md` from the issue.
  3. It re-points `state["url"]` to `openspec:ticket<N>` and `load_change` reads the **local**
     change. From that point generation runs **entirely offline** — no further GitHub calls.
  This is the bridge that makes the `ticket20`/`ticket22` e2e tests deterministic: the live fetch
  happens once, the result is mirrored as a local OpenSpec change (single source of truth), and
  every re-run regenerates that change via the CLI and runs locally. The change name is derived
  deterministically from the issue URL (`.../issues/20` → `ticket20`), so re-runs are idempotent.
  **The change `openspec/changes/ticket<N>/` is produced at runtime and MUST NOT be committed.**
- **OMISSION GUARD (contract-aware).** After generation, `make run-agentics` compares byte size of
  each generated file against its timestamped backup. A shrink is only a *genuine* omission if the
  generated file also **dropped the spec's contract command id** — a legitimate feature switch
  (e.g. greetings test < uuid test) produces a different-sized file, so pure byte-size comparison
  is a false positive. If the new contract command id is **present**, it is a successful generation —
  never restore. Only when the command id is **MISSING AND the file shrank** does the Makefile
  auto-restore the backup and flag it (the real B6/B11 omission case). When that happens you MUST
  then investigate *why* the Python agentic code dropped content (inspect `code_integrator` /
  `main_agent` / `code_extractor` write logic and the `export_name` deterministic-assembly rules)
  and fix the root cause before re-running.
- **RE-RUN AGENTIC TESTS AFTER GENERATION.** Once `make run-agentics` finishes (and the TS
  self-correct loop is green), the refactored Python agentic code MUST be re-verified: run
  `make verify-agentics-after-run` (which runs `test-agents-unit` + `test-agents-integration`).
  These tests MUST exercise **real logic** — unit tests test the real Python modules (mocking ONLY
  external calls: GitHub/Ollama/network/FS), and integration/e2e tests make **real** Ollama (and
  real GitHub where they fetch an issue) calls. If the agentic suite fails, the change is NOT done;
  report the failing test honestly. (Owned by the `agentic-tests-real-logic` change.)

### Phase 6 — Verify strictly against the spec (loop engineering + self-correction)
1. `make build-app` — builds the plugin via `containers/npm` (docker compose). Must exit 0.
2. `make test-app`  — runs jest via `containers/npm` (docker compose). Must pass.
3. Walk every `### Requirement` / `#### Scenario` / Acceptance Criterion in `specs/**/spec.md`
   and confirm it explicitly.
4. **Self-correction loop:** if build/test fails, the agentic pipeline's own
   `post_test_runner → error_recovery → code_integrator` cycle re-integrates and re-verifies.
   Re-run `make build-app` + `make test-app` until green. Be strict and honest in the verdict.

### Phase 7 — Document + decide next action
- Record the work with the scriptable tool (replaces the never-created `record-work` skill):
  `make record-work CHANGE=<name>` runs `scripts/record-work.py`, which collects the change's
  `proposal.md`/`tasks.md`/`specs/**`, `openspec status` + `openspec validate`, and git branch/commit,
  asks the project-manager Hermes CLI (`hermes -z`) to draft the prose, then writes
  `agent-wiki/YYYY-MM-DD-<name>.md` and updates `agent-wiki/index.md`. The entry captures:
  Date / OpenSpec Change / Branch / **Verification Against Spec** (per-requirement result) /
  Key Decisions / Current Status / Recommended Next Steps. (No git commit/push — B4/B14.)
- If all tasks done AND verification passes → archive the change with `make phase7-archive CHANGE=<name>`
  (merges specs into `openspec/specs/`). **NEVER run `git commit`/`git push` as part of archiving or
  generation** — that is a separate, explicit human step (see durable behaviours below).
- Otherwise → state clearly what is still missing.

### Durable agent behaviours (MUST always hold — never regress)

These behaviours are encoded in `hermes/skills/openspec-loop-harness.md` and enforced by
`make phase7-archive`. They are standing rules for the agent, not one-off tasks:

- **(B1) Persistent E2E test per generated-TS change.** Every OpenSpec change that makes the
  agentic pipeline generate TS code + TS tests MUST keep a runnable e2e test that reads THAT
  change's `tasks.md` (the spec task file) and asserts the generated Modal is wired + integrated.
  The standing harness is
  `agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py`. It MUST NEVER be
  removed when a change is archived or marked done. When the OpenSpec change is archived, only the
  *spec* is merged (`openspec archive`); the e2e test file stays in the repo permanently.
- **(B2) E2E reads the task file.** The e2e test loads `<repo>/openspec/changes/<CHANGE>/tasks.md`
  (and `spec.md`), confirms a "generate `<Feature>Modal` registered as a command" task is present,
  and asserts the generated `src/main.ts` contains that `obsidian.Modal` subclass wired via
  `this.addCommand(...)`. It validates against the change's own spec, not a hardcoded expectation.
- **(B3) E2E generates uniquely + is always runnable.** The e2e test runs the pipeline into an
  ISOLATED temp dir (unique per run) — never touches the real `src/main.ts`. Runnable any time;
  if it depends on a live Ollama/GitHub it skips cleanly without one. **Standing e2e gate (proof of
  concept) = THREE tests:** `test_ticket20_e2e_integration.py` + `test_ticket22_e2e_integration.py`
  (GitHub-issue seed-then-generate) + `test_greetings_e2e_integration.py` (LOCAL hand-authored change,
  the simple non-algorithmic proof). They MUST ALL pass after any Python slim/refactor. Greetings is
  the critical one: its modal is ABSENT from the committed `main.ts` baseline, so it proves the
  deterministic floor (not the baseline) injected the feature — uuid/ticket tests can pass by accident
  because the baseline already ships the uuid modal.
  - **(B5) E2E restores TS files to the COMMITTED baseline.** The e2e harness restores the
    repo's real `src/main.ts` / `src/__tests__/main.test.ts` to their **git HEAD (last
    committed)** state after every run — NOT to whatever was on disk before. So if generated
    task code already exists on disk but is uncommitted, the e2e rolls it back to the last
    commit; if it is already committed, it stays. The e2e can never leave uncommitted generated
    TS behind and always runs against a known-good committed baseline.
  - **(B6) If the generated task code already exists, still restore to committed state.** When
    the change's task code has already been generated (present on disk), the harness still RUNS
    and RE-GENERATES into the isolated temp dir to prove pipeline health, but writes nothing back
    to the repo and RESTORES the repo TS files to git HEAD afterward. It never commits/pushes and
    never keeps the regenerated code in the repo.
  - **(B4) NEVER commit/push when generated task code already exists.** The pipeline and the e2e
    harness MUST NOT call `git commit` / `git push` / `git add` / `git merge`. `make run-agentics`
    and `make phase7-archive` only write/archive TS + spec files; they never touch git. Committing
    and pushing generated `main.ts`/`main.test.ts` is a deliberate, separate human action.
  - **(B14) Commit/push gating for *new* code (human-only, behaviour-scoped).** A standing user
    rule: **code is committed ONLY if it is NEW, and pushed ONLY if that NEW code is part of a
    behaviour.** Concretely:
      1. The agent NEVER runs `git commit` / `git push` itself (extends B4). These are deliberate,
         separate **human** actions.
      2. Generated TS/`main.test.ts` produced by the pipeline is rarely "new behaviour" in the
         gating sense — it is the implementation of an already-approved OpenSpec change. It is
         committed/pushed only on the human's explicit go-ahead (e.g. "commit the uuid work").
      3. Floor/integrator fixes to `code_integrator_agent.py` ARE new behaviour-logic. They MAY be
         committed (and pushed only when that new logic forms part of a committed behaviour/change)
         **but ONLY once all of these hold**: `make build-app` exits 0, `make test-app` exits 0,
         the passing-test count is **greater than the previous run**, and all OpenSpec checks pass
         (`openspec validate <change>` + `openspec status --change <change>` are clean). The agent
         proposes the commit; the human pulls the trigger.
      4. Rule of thumb the agent follows: **commit only if new AND build-app works AND test-app works
         AND tests pass > last run AND all OpenSpec checks passed; push only if that new commit is the
         behaviour being landed.** Never squash/rebase/force-push (user hard requirement).
  - **(B15) GitHub issue → local OpenSpec change via the OpenSpec CLI (seed-then-generate).**
    When a change is sourced from a GitHub issue, the agentic code MUST turn it into a local
    OpenSpec change by **shelling out to `openspec new change ticket<N>`** (the same CLI step a
    human runs) — never by hand-writing the directory and never by a raw `Path.write_text` for the
    directory shape. `fetch_issue_agent.py` calls `openspec_loader.create_change_from_issue(url,
    title, body)` after the fetch; that function scaffolds via the CLI, then fills `proposal.md` /
    `specs/<cap>/spec.md` / `tasks.md` from the issue, and re-points generation to `openspec:ticket<N>`
    so the rest of the loop runs offline (no live GitHub). The change name is derived deterministically
    from the issue URL (`.../issues/20` → `ticket20`) so re-runs are idempotent. The seeded
    `openspec/changes/ticket<N>/` is a runtime artifact and MUST NOT be committed (extends B4); the
    `ticket20`/`ticket22` e2e tests generate + clean it up in `finally`. This keeps B10 honest: the
    exact `openspec new change` a human runs is the one the pipeline runs.
  - **(B16) Task-completion discipline — tick as you verify, never leave open tasks, archive gate
    fails closed.** The agent MUST tick each `tasks.md` checkbox (`- [ ]` → `- [x]`) the MOMENT the
    underlying work is actually finished AND verified — never complete work in code while leaving the
    checklist unticked (that desync caused 9 stale change dirs). The agent MUST keep grinding the
    loop-engineering backlog (`openspec/changes/*`) until every active change is fully ticked and
    archived, and MUST NOT stop mid-backlog unless the user explicitly says so. To enforce this
    mechanically: `make phase7-archive CHANGE=<name>` now runs
    `openspec_loader.assert_no_open_tasks` BEFORE `openspec archive` and **refuses (non-zero exit,
    no spec merge) if any `- [ ]` task remains**; `make loop-tasks` lists open/done counts per change
    so the backlog is never invisible. A change is "done" only when all its tasks are ticked AND
    verified AND archived (spec merge only — B4/B14 still forbid extra git commit/push). Code-fenced
    `- [ ]` lines inside `tasks.md` are NOT counted as open tasks.
    **Convention (closes the self-referential loophole): the final task in any `tasks.md` MUST be a
    *verification* that is tickable the moment the work is done — e.g. "openspec validate <name>
    passes" or "fast loop-integration subset green" — NEVER "run make phase7-archive". A task whose
    body is the archive command can never be ticked before the archive (chicken-and-egg), which
    defeated the tick-when-verified rule. Tick every task (including the final verification) BEFORE
    invoking archive; the archive command is the *last action*, not a task to be ticked.
    `tasks.md`/`spec.md` pins an exact contract (id / command name / Modal class — parsed by
    `CodeIntegratorAgent._expected_contract_for_change`), the integrator does NOT trust the LLM's
    generated command body. `generate_updated_code_file` routes to `_assemble_contract_features`,
    which string-only and idempotently: strips any non-contract `addCommand` + any existing/LLM
    Modal of that name from BOTH the existing file and the LLM output, injects the AUTHORITATIVE
    contract command body (exact id/name, calls the spec generator), and appends the spec Modal +
    spec generator ONLY if absent. The contract is derived from the spec text (`uuid v7` → `uuidv7`
    generator), never a hardcoded command string. This guarantees build/test pass even when the LLM
    under-delivers. The `code_generator_agent` prompt is tightened by injecting the same parsed
    contract as a "SPEC CONTRACT (honor EXACTLY)" bullet — prompt tightening comes from the spec
    file, NOT a literal string.
  - **(B17) Integration suite is a mandatory loop phase; no dead tests; live tests skip cleanly.** The
    agentic integration suite (`agents/agentics/tests/integration/*`) is a FIRST-CLASS loop gate, not
    an afterthought. `make loop-harness` (the authoritative loop-engineering stage) runs SEVEN stages
    in this exact order: a collection guard (gate 0) followed by six gates (1–6):
    `loop-collect` (hermetic collection guard — fail fast on dangling imports, see rule 4
    below) → `loop-unit` (mocked, hermetic) → `loop-unit-real` (REAL agent unit tests on live
    Ollama, no mocks) → `loop-e2e` (the 3 standing B1/B3 e2e gates) → `loop-integration` (broad agentic
    integration suite) → `loop-build-app` → `loop-test-app`. Each stage fails the whole run (no silent
    green). Rules for the integration tests themselves:
      1. **No dead tests.** When a file is a strict duplicate of another (or superseded by a canonical
         per-agent file), DELETE the duplicate — never keep two files asserting the same thing.
         (E.g. `test_jest_execution_integration_fixed.py` / `test_jest_execution_minimal.py` duplicate
         `test_jest_execution_integration.py` and were removed. The `integration-test-duplicate-audit`
         change confirmed the remaining suite has no strict duplicates — the only structural twin
         (`test_ticket20_e2e` ↔ `test_ticket22_e2e`) is a B3-mandatory distinct-capability gate, kept.)
      1b. **`loop-integration` runs the FAST subset only.** `loop-integration` invokes
         `test-agents-integration` with `INTEGRATION_TEST_FILTER="-m 'integration and not e2e and not slow'"`.
         This EXCLUDES (a) the 4 e2e files (already covered by the `loop-e2e` stage 3) and (b) tests tagged
         `@pytest.mark.slow` — the ~70 heavy full-pipeline (`process_issue`) tests that each fire the real
         multi-agent LLM pipeline and made the old full run take ~53 min. The slow tests are NOT deleted;
         they run via the explicit `make test-agents-integration` (full suite, incl. e2e + slow) for
         deliberate deep verification. This keeps `loop-integration` at ~6 min while preserving all
         necessary coverage. (Marker registered in `pytest.ini`; heavy files tagged in the
         `setup-loop-harness-openspec` work.)
      2. **Live tests skip cleanly.** Any test that needs a live Ollama endpoint
         (`OLLAMA_HOST`) MUST use `pytest.mark.skipif` so it SKIPS (not errors) when that
         dependency is absent — `make loop-integration` must exit 0 with a recorded skip count
         on a creds-less machine. **GitHub public-repository reads are token-less**, so
         `GITHUB_TOKEN` is NOT a skip condition (per the user correction during
         `integration-tests-lifecycle`): tests that only read public issues must run without a
         token and skip only on `OLLAMA_HOST`. Past edits applied this to
         `test_agentics_app_integration.py` + `test_configuration_integration.py`.
      3. **Categorization is provable.** The agent MUST keep an inventory (hermetic / live-Ollama /
         live-GitHub / dead) and reflect it in the active change's `tasks.md` so "the integration tests
         work and are updated (not just dead)" is demonstrable, not asserted.
      4. **Collection guard (fail-fast on dangling imports).** `make test-agents-collect` runs
         `pytest --collect-only` for BOTH `tests/unit/` and `tests/integration/` and is non-zero on any
         collection error. It is wired into `.github/workflows/test-on-commit.yml` so a slim-refactor
         that orphans a symbol (e.g. deletes a module a test still imports) FAILS CI instead of reporting
         a cached "green". This is the durable guard from the `audit-mcp-slim-refactor-integrity` change
         — never remove it. (B4/B14 still hold: no git commit/push from the loop.)
    This closes the gap where the broad integration suite was never a tracked gate and had drifted into
    un-categorized, partly-duplicated, partly-non-skipping files. (B4/B14 still hold: no git
    commit/push from the loop.)
  - **(B18) Run the agents' REAL unit tests, not only the mocked ones.** The loop MUST
    execute BOTH the hermetic mocked unit run (`loop-unit` → `make test-agents-unit-mock`)
    AND the real, non-mocked agent unit run (`loop-unit-real` → `make test-agents-unit`,
    live Ollama) as ordered gates 1 and 2 of `make loop-harness`. Reporting "agent tests
    green" after **only** the mocked run is INCOMPLETE — `loop-unit-real` is the proof that
    the deterministic floor + the agent units actually work against the live LLM (the unit
    under test is never mocked; only the Ollama/HTTP boundary may be). `make test-agents-unit`
    MUST be run when Ollama is reachable and its result reported alongside — not instead of —
    the mocked run. If Ollama is unreachable, `loop-unit-real` SKIPS (it must not error), but
    the agent MUST note that the real unit gate did not execute rather than silently treating
    the mocked run as the whole story. (This closes the gap where the agentic suite was
    reported green from the mocked run alone.)
  - **(B19) Archived change dirs carry a `YYYY-MM-DD-` prefix — resolvers and tests MUST handle it.** `openspec archive` moves `openspec/changes/<name>` to `openspec/changes/archive/<YYYY-MM-DD>-<name>`. Any code that locates a change by bare name — `openspec_loader.find_change_dir`, `CodeIntegratorAgent._expected_contract_for_change`, `run_pipeline_isolated` (e2e helper), and the contract/regression unit tests — MUST also match the date-prefixed archived variant (`archive/*-<name>`), otherwise those tests become dead tests pointing at a now-archived dir (violates B17). Likewise, the agentic code/tests resolve the repo root to wherever `openspec/changes` actually lives: in the unit/e2e containers the real repo is mounted at `/project` as a SIBLING of `/app` (only `/app/src` + `/app/tests` are mounted under `/app`), so a naive `../..` walk-up or `git rev-parse` from `/app` FAILS — resolve by probing for a dir that contains `openspec/changes` (never a fixed relative depth). The e2e/integration gates run the REAL pipeline against a live Ollama (`integration-test-agents` sets `OLLAMA_HOST=http://127.0.0.1:11434` — the loop/integration
 containers are rootless-nerdctl host-networked, so `host.docker.internal` does NOT resolve; the
 coordinate `127.0.0.1:11434` reaches the live Ollama on the docker host), so they must RUN (not
 skip) — root resolution is the actual bug to fix, not a skip guard.
  - **(B20) NEVER declare a change "done" without running the loop gate first — this is a hard pre-flight, not optional.** Before reporting any OpenSpec change as complete (or before claiming "the harness is green / aligned / fixed"), the agent MUST execute the loop gate and report its real output:
      1. **Preferred:** run `bash scripts/run-loop-harness.sh` (the loop-harness runner — it streams each stage's container/pytest/jest output to the terminal LIVE, prints a start banner + heartbeat on quiet stages, and ends with a per-stage PASS/FAIL/timeout summary; it wraps `make <stage>` in `setsid script … | tee` so nerdctl's forced `--tty` gets a console without deadlocking under an interactive shell). It runs all seven stages in order: `loop-collect` → `loop-unit` → `loop-unit-real` → `loop-e2e` → `loop-integration` → `loop-build-app` → `loop-test-app`. (The standalone `make test-agents-*` / `make run-agentics` commands also self-provide a console via the Makefile `$(call docker_run, …)` helper, which uses `script` only when stdout is not a tty.)
      2. **If the full `make loop-harness` cannot complete in the session** (e.g. `loop-e2e`/`loop-unit-real` need a live Ollama that is not reachable, or `build-app`/`test-app` time out), the agent MUST STILL run the **hermetic gates** — `make loop-collect` and `make loop-unit` — and report their real results. The hermetic gates need NO external dependency and MUST be green before any "done" claim.
      3. **Report honestly.** State the actual per-stage outcome (PASS / SKIP / FAIL with the failing stage named). Never say "done/green" if `loop-unit` (or `loop-collect`) is red. If a gate fails, fix the root cause and re-run — do not hand-edit generated output to fake green, and do not stop at doc/alignment edits while a code gate is failing.
      Rationale: in prior runs the agent repeatedly finished work (including AGENTS.md/skill edits) WITHOUT running the gate, leaving `make loop-unit` red and only discovering it later. B20 makes the gate a mandatory final step so regressions are caught before "done" is claimed. (B4/B14 still forbid git commit/push from the gate.)
  - **(B21) HITL is OPT-IN and loop-excluded — never a blocking prompt in automation.** The `HITLNode`
     (`src/hitl_node.py`) only prompts a human (calls `input()`) when ALL hold: validation score `< 80`,
     not in CI, `HITL_ENABLED=1`, `INTERACTIVE_HITL=1`, and `sys.stdin.isatty()` is true. In the loop /
     CI / `make run-agentics` automated runs none hold, so the node returns `state` UNCHANGED — a no-op
     pass-through, and the `human_feedback` key is NOT added. HITL is a deliberate feature for a human at
     a terminal, NOT a gate the loop depends on. Any automated HITL test MUST assert the **pass-through**
     (state unchanged, no `human_feedback`), never the interactive-only key (that assertion is flaky in the
     loop). The two-flag gate prevents a leaked `HITL_ENABLED` from a killed test from ever blocking the
     loop on `input()`. (Captured in the `hitl-optin-loop-excluded` OpenSpec change + `hitl-optin` spec.)
     B8 sync: this behaviour is documented here, in `hermes/skills/openspec-loop-harness.md`, and in the
     `hitl-optin` spec — keep all three in agreement.
  - **(B22) Release automation is a POST-GREEN loop-engineering stage, never part of the 7-stage
     verification gate, and NO push.** The Makefile prepares a release LOCALLY; the actual GitHub
     release is cut by CI (`.github/workflows/release.yml`, on merge to `main`). Local commands:
       - **`make bump-local`** — LOCAL staging: `check-released` → `bump-version` (Obsidian way:
         `package.json` + `manifest.json` + `versions.json`) → `tag-release` (LOCAL tag only). NO
         squash-commits, NO changelog, NO release-notes, NO push. Use this to advance the version
         locally (e.g. `make bump-local PART=patch`).
       - **`make squash-commits`** — squash to one TYPED Conventional commit (see below).
       - **`make changelog`** — regenerate sectioned `CHANGELOG.md`.
       - **`make release-notes`** — refresh the README release-notes block.
       - **`make release-prep`** — the local publish-prep wrapper: `check-released` → `bump-version`
         → `squash-commits` → `changelog` → `release-notes` → `tag-release` (LOCAL tag only). The
         GitHub release itself is done by CI on merge to main. NO push (B14).
       - **`make loop-release`** — loop-facing variant: same steps, but NO-OP if no generated TS
         changed vs HEAD, and runs `check-released` first.
     `check-released` FAILS if the CURRENT `package.json` version is ALREADY released on GitHub
     (remote tag `<version>` OR `v<version>`, tolerant of both forms) OR does NOT advance past the
     latest released version (no semver gap) — so a bump only happens when not-yet-released AND
     there is a real forward gap. It FAILS-CLOSED if `gh`/network is unavailable. The squashed
     commit's Conventional `type(scope):` prefix is the SINGLE SOURCE OF TRUTH: `squash-commits`
     FORCES a valid `type(scope):` first line and FAILS-CLOSED if untyped, driving BOTH the changelog
     section (feat→✨, fix→🐞, docs→📝, refactor→🔧, chore→🛠️) AND the bump semantics. Pushing commit +
     tag is a deliberate human action that triggers CI to publish. (NOTE: the pre-existing `release`
     Makefile target is the CI build-zip step — left intact for `release.yml`; do NOT reuse it for
     local prep.)
     B8 sync: documented here, in `hermes/skills/openspec-loop-harness.md`, and in the
     `release-automation` spec.
  - **(B7.1) The deterministic floor runs in EVERY mode (incl. fast).** `route_hitl` in
    `composable_workflows.py` previously returned `output_result` when `TEST_FAST_MODE=1` (set by
    `tests/integration/conftest.py` to skip the npm-test phase), which bypassed `integration_testing`
    — the ONLY sub-graph containing `code_integrator`. That left the spec contract uninjected and the
    raw LLM output in `main.ts` (a B10/B11 violation). The greetings e2e exposed it: uuid passed only
    because the committed `main.ts` baseline already ships the uuid modal. FIX: fast mode now routes
    `code_generation → code_integrator (floor) → output_result`, so the sole-writer ALWAYS runs; fast
    mode only skips the npm-test loop. Slow mode is unchanged. Do NOT reintroduce a fast-mode shortcut
    that bypasses `code_integrator`.
  - **(B8) Skill ↔ AGENTS.md bidirectional sync (never drift).** `AGENTS.md` and
    `hermes/skills/openspec-loop-harness.md` are the SAME source of truth for this repo's
    harness behaviour. Any change to a behaviour, constraint, command, or pitfall in ONE file
    MUST be mirrored in the OTHER before the change is considered done. When editing `AGENTS.md`,
    load the skill (`skill_view openspec-loop-harness`) first; when editing the skill, re-read
    `AGENTS.md` first. Never leave the two files describing different behaviour.
  - **(B9) Rootless nerdctl bind-mount permissions (READ + WRITE).** Execution is docker compose
    with **rootless nerdctl**, which remaps the container uid (1000) to the host **`other`** class.
    Every file/dir the container must READ (the whole repo, since compose mounts `..:/project`)
    MUST be world-readable + traversable: `chmod -R a+rX <repo>`. Every path the container must
    WRITE (`src/`, `backups/`, `openspec/.../specs`, `/project/results`, `.cache`) MUST be
    world-writable: `chmod -R a+rwX <write-targets>`. A missing `o+r`/`o+x` surfaces as
    `PermissionError: [Errno 13]` from the agent mid-run (e.g. reading a change `spec.md`, or
    writing `src/main.ts`). **ENFORCED BY THE MAKEFILE:** the `b9-perms` target applies both
    `chmod` commands and is a PREREQUISITE of `run-agentics` / `build-app` / `test-app`, so it
    runs automatically at the start of any such invocation — no manual step required (and never
    rely on group/owner perms alone). Run `make b9-perms` manually only if invoking docker compose
    outside the Makefile. World-readable on a private repo is acceptable.
  - **(B10) NO hard-coded generated TS/test code in Python — only contract-steered.** When an
    OpenSpec change makes the agentic pipeline generate TypeScript (a command, Modal, generator
    method, or its tests), **the authoritative TS bodies MUST live ONLY in the change's `tasks.md` /
    `spec.md`** (a fenced ```` ```ts ```` block, split by `=== CONTRACT_* ===` / `=== TEST_CONTRACT_* ===`
    markers). `code_integrator_agent.py` (and ALL Python) MUST NOT contain any generated TS/test
    *bodies* as string literals — no `addCommand({...})`, no `class X extends obsidian.Modal {...}`,
    no `generateUuidV7() {...}`, no `describe(...)`/`it(...)` test bodies. Python only: (a) parses the
    spec markers via `_expected_contract_for_change`, (b) performs the deterministic *merge* (anchors:
    imports / `onload()` / class closing brace / file end / describe boundaries), and (c) injects the
    spec's exact contract TS verbatim. The only acceptable spec-derived tokens in Python are
    *identifiers used for idempotency guards* (e.g. checking `class UuidV7Modal extends obsidian.Modal`
    is already present) — never the body text. **Verification:** `grep -nE
    "addCommand\(|extends obsidian\.Modal|describe\('|it\('|test\('" agents/agentics/src/*.py`
    must return ONLY comments / docstrings / idempotency-guard regexes, never TS body literals.
    This keeps the spec as the single source of truth: changing generated code = editing the OpenSpec
    change, not the Python.
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
  - **(B12) Delivery gap — the verified worktree TS MUST reach the active branch.** The
    agentic pipeline generates + verifies TS **inside a git worktree** (`worktrees/<name>`,
    branch `feat/<name>`). The harness MUST NOT stop there: a feature that is green only in the
    worktree and never lands on the branch it targets is a failed delivery. After `make
    build-app` + `make test-app` are green in/for the worktree, the agent MUST pull the verified
    `src/main.ts` + `src/__tests__/main.test.ts` back onto the **current branch's working tree**
    (e.g. `make deliver-change CHANGE=<name>`, which copies the worktree files into the repo tree).
    This is a file copy only — it does NOT commit/push (B4); committing remains a deliberate human
    step. The agent must NEVER declare a change "done" while its generated TS still lives only in
    the worktree. (Pitfall: AGENTS.md Phase 5's "the old TS remains until you deliberately merge
    the worktree" previously let verified code die in the worktree — B12 overrides that silence.)
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

---

## Harness / loop-engineering rules (self-correcting behaviour)

- **The four artifacts are ONE source of truth — never let them drift.** The loop/harness
  discipline is defined identically in exactly four places, and any edit to one MUST be mirrored in
  the others (this is B8):
  1. **`Makefile`** — the executable gates: `make loop-harness` = `loop-unit` → `loop-unit-real`
     → `loop-e2e` → `loop-integration` → `loop-build-app` → `loop-test-app`; plus `make phase7-archive`
     (B16 open-task guard + B1 e2e-harness guard, then `openspec archive -y`), `make run-agentics`,
     `make build-app`/`test-app`, `make deliver-change`, `make loop-tasks`.
  2. **`AGENTS.md`** — this file: the authoritative narrative + the B1–B18 durable behaviours.
  3. **`hermes/skills/openspec-loop-harness.md`** — the loadable skill mirror of AGENTS.md.
  4. **The e2e harness** `agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py`
     + the 3 standing e2e gates (`test_ticket20_*` / `test_ticket22_*` / `test_greetings_*`, all
     marked `@pytest.mark.e2e`) — the runtime proof the loop works.
  Before claiming "the loop is green / aligned", confirm all four agree on the 6-gate order, the
  B1–B18 behaviours, the live-test skip rule (`OLLAMA_HOST` only, not `GITHUB_TOKEN`), and that
  `phase7-archive` actually archives (non-interactive `-y`). A change is NOT done while any of the
  four disagree.
- The harness is the OpenSpec change: `proposal.md` defines *why*, `specs/**` defines *what must
  hold*, `tasks.md` defines *the steps to run*. The agentic pipeline turns tasks into code+tests.
- Verification is the gate that defines "done": `make build-app` + `make test-app` + spec walk-through.
- On failure, loop (re-run agentics / fix / re-verify) — do not declare done until the loop is green.
- The old `src/main.ts` and `src/__tests__/main.test.ts` must remain available (worktree isolation);
  only the generated versions in the worktree are what get verified.

## General Rules
- The OpenSpec spec ALWAYS wins over your own ideas.
- `tasks.md` is the executable plan for both you and the agentic pipeline — keep it in checkbox format.
- Use `llm-wiki` for documentation; keep wiki entries useful and concise.
- Create new skills only when you repeat the same work. Stay focused. Avoid scope creep.
- Never delete `agents/` (project Python code) when "removing agent skills" — that means IDE/agent config only.
- No Dagger, no MCP: execution is `docker compose` only (`containers/` + `docker-compose-files/`).
- **`requirements.txt` is ALWAYS regenerated, never hand-edited.** The single source of truth is
  `docker-files/pip-requirements/requirements.in`. Run `make generate-requirements` to compile it
  into `agents/agentics/requirements.txt` (via the `containers/pip` pip-compile image). If a
  `ResolutionImpossible` conflict appears while building the `agentics` image, fix it in the
  **`.in`** file (e.g. pin a transitive dep there) and re-run `make generate-requirements` —
  do NOT patch the generated `requirements.txt` by hand. The same applies to `docker-files/pip-requirements/requirements.txt`.
- **Agent skills:** the project skill `hermes/skills/openspec-loop-harness.md` is the
  authoritative reference for this repo's OpenSpec loop, docker-compose-only execution,
  requirements regeneration, and the backup/omission-guard behaviour. Load it
  (`skill_view openspec-loop-harness`) whenever you work an OpenSpec change, the Makefile,
  `containers/`, or the agentic pipeline here.
