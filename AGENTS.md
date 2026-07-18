# Project Instructions for Hermes Agent (OpenSpec Workflow)

You are working in a spec-driven project using **OpenSpec** (CLI `@fission-ai/openspec`, installed
as an npm devDependency — run via `make openspec-new` / `openspec validate`).
The source of truth for any change is an OpenSpec **change** under `openspec/changes/<name>/`
containing `proposal.md`, `tasks.md`, optional `design.md`, and `specs/<capability>/spec.md`.
The Python agentic pipeline (`agents/agentics`) **reads these local files** (not GitHub) to
generate and test TypeScript — driven through the Makefile. All execution runs via Docker
compose (no Dagger, no MCP).

**Execution environment — EXECUTE THROUGH `make` (do not hand-run, never make excuses).** The agent's
working tree is this repo. There are TWO execution contexts and you MUST use the right one:
- **Foreground `terminal` calls** run inside the agent **sandbox** at `/workspace` — a bind-mount of
  the repo. This is where file edits (`write_file`/`patch`), `git` (read-only), `openspec` (npm
  devDep, installed in `node_modules`), and quick checks happen. The sandbox has NO `docker`/
  `nerdctl`/Ollama binary.
- **`terminal(background=true)` calls run on the REAL HOST** at
  `/home/asimov/repository/git/projects/obsidian-timestamp-utility` — the same git worktree, just a
  different mount point. The host HAS `make` (`/usr/bin/make`), `docker` (`/usr/bin/docker`),
  `nerdctl` (`/home/linuxbrew/.linuxbrew/bin/nerdctl`, rootless), and a **live Ollama** reachable
  from the host-networked loop containers at `127.0.0.1:11434` (B19).
  **RULE: every long-running verification step (`make run-agentics`, `make build-app`, `make test-app`,
  `make loop-harness`, `make loop-e2e`, `make deliver-change`, `make phase7-archive`, `make release-flow`)
  MUST be launched via `terminal(background=true)` so it executes on the host where the runtime lives.
  The foreground sandbox will report `docker: command not found` — that is EXPECTED there and is NOT
  a blocker; the host has it.** Never say "can't run from here" / "environment absent" — the host
  executes `make` for you. Drive verification through `make` with REAL output, always.

The host provides everything the Makefile targets need:
- **rootless `nerdctl` / docker compose** — `make loop-harness`, `make build-app`, `make test-app`,
  `make run-agentics`, `make loop-e2e`, etc. spin up REAL containers on the host.
- **a live Ollama** on the host, host-networked so `127.0.0.1:11434` from inside a container reaches
  it (B19). `loop-unit-real` and `loop-e2e` are EXPECTED to RUN against live Ollama (not skip).
- **`openspec`** is an npm devDependency (`npm install` makes the CLI available in `node_modules/.bin`),
  so `make openspec-new` / `openspec validate` / `openspec archive` work via the real CLI (B15).
  Invoke it through `make`, never by hand-writing change dirs.

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
resort, B13). The durable behaviours B1–B34 are the loop's "laws of physics" — invariants that
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
git worktree add ../worktrees/<name> -b wt/<name>
cd ../worktrees/<name>
```
- **EACH OpenSpec change gets its OWN parallel worktree (standing rule, see B24 + B27).** Creating an
  OpenSpec change (`make openspec-new NAME=<name>`) and the implementation work for it MUST run in a
  dedicated linked worktree keyed by the change name — never on the parent branch directly. The
  worktree is the change's sandbox: it may be `reset`/`checkout`/regenerated freely WITHOUT ever
  touching the parent branch's history or uncommitted work. **By default (B27) this sandbox is a
  LOCAL throwaway branch `wt/<name>` — the agent creates NO `feat/<name>` branch and pushes nothing
  to a remote unless the human explicitly says "make the PR".** Flow:
  1. `make openspec-new NAME=<name>` scaffolds `openspec/changes/<name>/` on the **parent** (it is the
     spec of record; the change dir itself lives on the parent, see B15/B19).
  2. `git worktree add ../worktrees/<name> -b wt/<name>` spawns the isolated implementation sandbox.
  3. Do ALL implementation + agentic generation + verification INSIDE `../worktrees/<name>`. The
     `loop-green-auto-squash-changelog` / `loop-finish` style finalisation also runs there.
  4. When the change's `tasks.md` is fully ticked AND `openspec validate <name>` + the loop gate are
     green, and ONLY when the human explicitly requests delivery (B27): promote `wt/<name>` →
     `feat/<name>`, push `origin feat/<name>`, and open the PR (parallel-safe: unique branch +
     `COMPOSE_PROJECT_NAME=otu-<name>`). Otherwise keep the work in the local sandbox; do NOT sync
     back to the parent unless the human asks.
  5. If a worktree's compose `make` targets fail on mount-root resolution (B19), run the underlying
     scripts directly in the worktree (B24 rule 4) — the worktree is still the safe iteration space.
  This guarantees the parent branch is never corrupted by a failed/abandoned change: a broken change
  is abandoned by deleting its worktree + `wt/<name>` branch, leaving the parent untouched.
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
- **`phase7-archive` auto-emits the work-log.** `make phase7-archive CHANGE=<name>` runs
  `scripts/record-work.py` automatically after `openspec archive` succeeds, so archiving a change
  also writes its `agent-wiki/YYYY-MM-DD-<name>.md` entry — no separate `make record-work` call is
  needed. `make record-work CHANGE=<name>` remains callable standalone for re-runs. (B4/B14: only
  wiki files are written, never git commit/push.)
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
    an afterthought. `make loop-harness` (the authoritative loop-engineering stage) runs TEN stages
 in this exact order: a collection guard (gate 0), a strict TS test/command floor (gate 0.5),
 followed by six gates (1–6):
 `loop-collect` (hermetic collection guard — fail fast on dangling imports, see rule 4
 below) → `loop-ts-floor` (STRICT TS test/command floor — FAIL if the current branch's
 `describe`/leaf `it`/`test`/jest-collected/`addCommand` counts drop below `origin/main`;
 the silent feature/test-removal guard, see behaviour `ts-test-floor`) → `loop-unit` (mocked,
 hermetic) → `loop-unit-real` (REAL agent unit tests on live
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
      5. **A green gate MUST NOT rely on FALSE skips.** A skip is legitimate ONLY when its required
         dependency is genuinely absent (no `OLLAMA_HOST`, no `/project/src/main.ts` reachable, etc.).
         A skip whose dependency IS present is a **false skip** and is a GATE DEFECT — it lets
         `make loop-harness` report green while real coverage is silently lost. The agent MUST, after
         every loop run, inspect the skip list and confirm each skip's reason is **true**; any false
         skip MUST be fixed (root cause: usually a wrong path/root resolution or a stale skip reason),
         never left as-is. Concretely: the integration container mounts the repo root at BOTH `/app` and
         `/project`, but compose bind-mounts the agentics Python source onto `/app/src`, which SHADOWS
         the repo's own `src/main.ts` (TypeScript). Root resolution (`_repo_root()`) MUST prefer the
         unshadowed mount (`/project`, which contains `src/main.ts`) so the e2e contract tests RUN
         instead of falsely skipping with "No src/main.ts in repo". A skip at
         `test_change_driven_ts_generation_e2e.py:204` on a host where `/project/src/main.ts` exists is
         a defect, not a pass.
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
      1. **Preferred:** run `bash scripts/run-loop-harness.sh` (the loop-harness runner — it streams each stage's container/pytest/jest output to the terminal LIVE, prints a start banner + heartbeat on quiet stages, and ends with a per-stage PASS/FAIL/timeout summary; it wraps `make <stage>` in `setsid script … | tee` so nerdctl's forced `--tty` gets a console without deadlocking under an interactive shell). It runs all stages in order: `loop-collect` → `loop-ts-floor` → `loop-unit` → `loop-unit-real` → `loop-e2e` → `loop-integration` → `loop-build-app` → `loop-test-app` → `loop-release-dryrun` → `loop-release-tests` → `loop-secret-scan-tests` → `check-docs-sync`. (The standalone `make test-agents-*` / `make run-agentics` commands also self-provide a console via the Makefile `$(call docker_run, …)` helper, which uses `script` only when stdout is not a tty.)
         **HOW TO RUN (never make excuses):** long-running `make` targets (`run-agentics`, `build-app`, `test-app`, `loop-harness`, `loop-e2e`, `deliver-change`, `phase7-archive`, `release-flow`) MUST be launched via `terminal(background=true)` — that call executes on the **REAL HOST** (`/home/asimov/repository/git/projects/obsidian-timestamp-utility`), where `make`/`docker`/rootless `nerdctl`/live Ollama all live. The foreground sandbox (`/workspace`) has NO docker/nerdctl and will print `docker: command not found` — that is EXPECTED and is NOT a blocker; the host has it. **Never say "can't run from here" / "environment absent" — the host runs `make` for you.** Drive verification through `make` with REAL output, always.
      2. **If the full `make loop-harness` cannot complete in the session** (e.g. an explicit
         timeout, or a stage is deliberately disabled via env), the agent MUST STILL run the
         **hermetic gates** — `make loop-collect`, `make loop-ts-floor`, and `make loop-unit` — and report their real
         results. The hermetic gates need NO external dependency and MUST be green before any
         "done" claim. NOTE: a live Ollama IS reachable from the loop containers (the host runs
         Ollama and the rootless-nerdctl containers are host-networked, so `127.0.0.1:11434`
         reaches it — see B19) — so `loop-unit-real` and `loop-e2e` are EXPECTED to RUN, not skip.
         Do not assume Ollama is unavailable; only fall back to hermetic-only when a stage truly
         cannot run in the session.
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
       - **`make squash-commits`** — squash ALL commits ahead of `main` into ONE TYPED Conventional
         commit. FAIL-CLOSED (a) if the first line is untyped, and (b) if the drafted message fails
         `commitlint` (`lint-commits` gate, using `commitlint.config.cjs`). On either failure the
         pre-squash state is restored (`git reset --quit <main>`) and no commit is created. This is
         the "tag it accordingly" guarantee: the `type(scope):` prefix drives BOTH the CHANGELOG
         sections AND the bump PART.
       - **`make lint-commits`** — run `commitlint` over the squashed range / HEAD; the changelog lint
         gate (fail-closed on any invalid message).
       - **`make install-git-hooks`** — wire `git-hooks/commit-msg` (per-commit Conventional-Commit
         lint) and `git-hooks/pre-commit` (trailing-whitespace auto-fix) into `.git/hooks` so every
         manual `git commit` is linted. The pre-commit hook only strips trailing whitespace from
         staged text files and **never exits non-zero**, so it is inert under the loop (which performs
         no `git commit`).
       - **`make changelog`** — regenerate sectioned `CHANGELOG.md` (git_chglog; one `## <version>`
         section per git tag, so a local `v<version>` tag after bump yields a viewable new section).
       - **`make release-notes`** — refresh the README release-notes block.
       - **`make release-flow`** (canonical, LOCAL only, NO push) — runs in the user's exact order:
         `squash-commits` (typed, commitlint-gated) → `bump-local` (Obsidian-way bump to the NEXT
         UNRELEASED version, guarded: refuses unless NEW plugin TS exists in `src/main.ts` vs
         `origin/main`, AND `check-released` passes — no semver gap, not already released) →
         `changelog` (regenerate CHANGELOG.md with the new `## <version>` section) → `release-notes`.
         This is the single command that "squash, tag accordingly, then bump to the next unreleased
         version (only when new TS changed), then view it in the changelog."
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
     FORCES a valid `type(scope):` first line AND passes it through `commitlint`, driving BOTH the
     changelog section (feat→✨, fix→🐞, docs→📝, refactor→🔧, chore→🛠️) AND the bump semantics. Pushing
     commit + tag is a deliberate human action that triggers CI to publish. (NOTE: the pre-existing
     `release` Makefile target is the CI build-zip step — left intact for `release.yml`; do NOT
     reuse it for local prep.)
     B8 sync: documented here, in `hermes/skills/openspec-loop-harness.md`, and in the
     `release-automation` spec.
  - **(B23) NEVER let a pipeline/release fix die in the working tree — COMMIT fix-work before any
     reset-capable verification.** A `git checkout -- <files>` / `git reset --hard` (or any test
     harness that resets the tree) DESTROYS uncommitted work permanently. The 2026-07-15 incident: the
     changelog/bump pipeline was repaired in uncommitted scripts, then a verification step ran
     `git reset --hard origin/main` to clean up — wiping every fix (Makefile target, `gen_changelog.sh`,
     `merge_changelog.py`, `bump_from_changelog.py`); the loop re-broke and the same bugs were re-fixed
     from scratch. RULES that make this impossible to repeat:
       1. **Commit the moment a fix is written.** As soon as a script/Makefile change that fixes the
          release/build/generation pipeline is complete AND passes a local syntax/unit smoke check,
          `git commit` it (a separate, deliberate commit — NOT buried in the squash-commits release
          flow). Committed work survives any `git reset --hard origin/main`/`git checkout --`.
       2. **Verify against committed state, not uncommitted.** Run idempotency/loop tests from a state
          where the fix is already committed (or `git stash`/commit first), so a reset in the test
          cannot eat it. If a test harness must reset the tree, reset to the LAST COMMIT that INCLUDES
          the fix, never to a bare `origin/main` that predates it.
       3. **Test cleanup must not lose authored fixes.** A test that creates throwaway commits/tags
          must remove ONLY the throwaway artifacts (`git reset --soft HEAD~1`, `git tag -d <temp>`),
          never `git reset --hard origin/main`. `git checkout --` only for files the test itself wrote,
          never for the source fix.
       4. **No multi-file fix left uncommitted across a tool-call boundary.** If a fix spans >1 file
          and the next action could reset the tree, commit after EACH file (or at minimum after the
          batch) before running any reset-capable command. The cost of an extra commit is zero; the
          cost of re-deriving a lost fix is hours.
       5. **Green-gated release finalisation uses `make loop-finish`.** When the loop gate is GREEN
          (B20 pre-flight: `make loop-harness` passes) and the OpenSpec backlog is clear (every active
          change has open=0), finalise the release LOCALLY with `make loop-finish`. It runs, in order:
          `assert-backlog-clear` (FAILS CLOSED if any active change has an open task) →
          `archive-all-complete` (archives every active change via `phase7-archive`, B16 gate per
          change) → `squash-commits` (one TYPED Conventional commit) → `changelog` →
          `bump-from-changelog` → `changelog-format`. It MUST NOT push (B4/B14) — pushing the squashed
          commit + tag is a deliberate human action. `loop-finish` is the single command that performs
          the "squash + changelog + bump" end-state the loop-agent must drive when green; never hand-run
          the steps piecemeal and never run it on a red gate or with open tasks.
     This is permitted under B14: B14 forbids committing *generated TS output* and *pushing*; it does
     NOT forbid committing genuine fix-work the human has directed. Commits are still local (no push)
     unless the human triggers CI. B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md`.
  - **(B24) NEVER `git reset --hard` / `git checkout --` / delete commits on the PARENT branch — work
     ONLY inside an isolated WORKTREE (or throwaway branch) and SYNC BACK when green.** The agent is
     forbidden from destroying history or uncommitted work on the active/parent branch. Any operation
     that *could* lose work (`reset --hard`, `reset --mixed` past authored commits, `checkout --` on
     source files, `branch -D` of a branch holding fix-work, `clean -fd`) MUST instead run inside a
     sandbox that cannot touch the parent:
       1. **Spawn a linked worktree per risky task.** `git worktree add ../worktrees/<name> -b
          wt/<name>` and do ALL exploratory/editing/reset/checkout/test work THERE. The worktree is a
          full isolated checkout; `reset --hard`/`checkout` inside it only affects the worktree, never
          the parent. When it is green, **sync back** to the parent: `git merge wt/<name>` (or
          `git cherry-pick` the squashed result) from the parent branch, then `git worktree remove`.
       2. **If a worktree is impractical** (e.g. compose mount-root issues — see B19), use a throwaway
          branch off the parent (`git branch wt/<name>` / `git checkout -b wt/<name>`) and do the risky
          work there; `reset`/`checkout` on `wt/<name>` cannot destroy the parent's commits. Merge back
          when green, then delete `wt/<name>`. A throwaway branch is a LIGHTWEIGHT backup, not the
          forbidden `reset --hard`.
       3. **The parent branch is read-mostly.** The agent may `git commit` (B23) and `git merge`/`git
          cherry-pick` onto the parent, but MUST NOT `reset`/`checkout` it back past authored work, and
          MUST NOT `branch -D` a branch that holds un-synced fix-work. If a parent reset is ever truly
          required, the human must do it — not the agent.
       4. **Verify the sandbox works first.** Compose-based Makefile targets resolve the repo root via
          relative `..` (B19); a worktree at `../worktrees/<name>` changes that resolution, so `make`
          container targets may fail inside a worktree. If so, run the pipeline's underlying scripts
          directly in the worktree (e.g. `bash scripts/gen_changelog.sh`, `python3 scripts/...py`) to
          validate logic, and reserve the docker-compose `make` targets for the parent/CI. The worktree
          is still the safe place to iterate — just invoke the logic, not the compose wrapper, when the
          mount root mismatches.
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md`.
  - **(B25) NEVER squash/merge-squash commits on the current branch without EXPLICIT human
     approval in that branch.** The agent is forbidden from running `make squash-commits`,
     `git rebase -i`/`-i` that picks `squash`/`fixup`, `git reset --soft` + `git commit` to collapse
     history, or any other operation that COLLAPSES/COMBINES commits on the branch it is working in
     unless the human has explicitly said to (e.g. "squash it", "run squash-commits"). This is a hard
     gate, separate from B14 (no-push) and B24 (no parent reset): the human owns the commit graph.
       1. The agent MAY `git commit` (B23) and `git merge`/`git cherry-pick` onto the parent freely,
          but MUST leave the existing commit structure intact — it must not rewrite/squash it.
       2. If history IS messy (e.g. throwaway test commits leaked in), the agent FLAGS it for the
          human and asks whether to squash — it does NOT decide unilaterally.
       3. `make squash-commits` is a HUMAN-TRIGGERED command only. The agent may mention it as an
          option, but must not execute it unless the human approved it for the current branch.
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md`.
  - **(B26) AGENT MAY COMMIT AND PUSH ITS OWN CHANGES on a non-main branch when the LOOP GATE IS
     GREEN and the PRE-COMMIT HOOK PASSES.** The agent is permitted to `git commit` (and
     `git merge`/`git cherry-pick`, and `git push` to its OWN feature/PR branch) its OWN
     work-in-progress — e.g. landing this branch's OpenSpec change, scripts, Makefile, and
     doc-sync edits — so the remote stays synced without a human hand-driving every step. Bounded:
       1. **Branch guard:** the current branch MUST NOT be `main` or `origin/main` (nor any other
          protected branch). On `main`, B4/B14/B25 still forbid the agent from committing/pushing on
          its own — a human triggers that.
       2. **Hook guard:** the `git-hooks/pre-commit` (gitleaks secret scan + trailing-whitespace) MUST
          pass. The agent commits ONLY through the normal `git commit` path so the hook runs; it
          NEVER uses `--no-verify`.
       3. **Loop-gate guard (push only after green):** the agent pushes its branch ONLY after the
          OpenSpec/loop gate is GREEN for the change it is delivering — i.e. `make build-app` exit 0
          + `make test-app` pass AND/OR `make check-docs-sync` PASS for doc-only changes (B20). It
          MUST NOT push red work. This is the sync-to-remote step that keeps the feature branch
          current on the remote (so a PR can be opened / kept up to date) — it is NOT a push to `main`.
       4. **Still forbidden (human-only):** `git push` to `main`/`origin/main` (B14), `make
          squash-commits`, `git rebase -i` with squash/fixup, and `git reset --soft` + collapse (B25).
          This behaviour ADDS commit/merge/**push-to-own-branch** latitude on feature branches; it
          does NOT lift the no-push-to-main / no-squash / no-force gates.
       5. Commits should be atomic and conventionally-scoped (the `git-hooks/commit-msg` lint applies).
          The agent keeps `tasks.md` ticked as work is verified (B16) and re-runs `make check-docs-sync`
          whenever it edits a sync doc, committing + pushing the result so AGENTS.md / the skill / the
          harness doc stay in lockstep on the remote too.
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md` and
     `docs/openspec-engineering-loop-harness.md`.
  - **(B27) AGENT WORKS IN A LOCAL WORKTREE SANDBOX, THEN AUTO-DELIVERS THE PR ON COMPLETION — EVERY
     TIME.** For every OpenSpec change the agent's working mode is an isolated **local** git worktree
     sandbox (`worktrees/<name>` on a throwaway branch `wt/<name>`): it does its implementation,
     generation, loop gate, and archive THERE, and it creates NO `feat/<name>` branch and pushes
     NOTHING during the work — the parent working tree stays untouched. **As soon as the change is
     COMPLETE** (all `tasks.md` checkboxes ticked AND the loop gate is GREEN AND the pre-commit hook
     passes — B26's guards), the agent **AUTOMATICALLY** promotes `wt/<name>` → `feat/<name>`, pushes
     `origin feat/<name>`, and opens the PR — **every time, by default, with no second "make the PR"
     prompt.** Green-lighting a change IS the delivery authorization; completion triggers delivery.
     Bounded + parallel-safe:
       1. **Sandbox during work:** `git worktree add ../worktrees/<name> -b wt/<name>`; all change work
          lives there; the parent working tree is never touched; no remote branch exists yet.
       2. **Auto-deliver on completion:** once `tasks.md` is fully ticked AND `openspec validate <name>`
          + the loop gate pass AND `git-hooks/pre-commit` is green, the agent promotes `wt/<name>` →
          `feat/<name>`, pushes `origin feat/<name>`, and opens the PR without further prompting.
       3. **Parallel-safe:** each change uses a UNIQUE worktree (`worktrees/<name>`), a UNIQUE branch
          (`wt/<name>` during work, `feat/<name>` on delivery), and a UNIQUE compose project name
          (`COMPOSE_PROJECT_NAME=otu-<name>`). Many agents can each iterate in their own sandbox and
          deliver their own distinct PR branch concurrently with no collision.
       4. **This is the default flow:** `make openspec-flow NAME=<name>` (and `wt-create`,
          `openspec-change-flow.sh`) create the local `wt/<name>` sandbox, run the gate, and — on
          green — automatically promote + push + open the `feat/<name>` PR. `PUSH=1`/`--push` is
          retained as an explicit alias but is now the default behaviour, not an opt-in.
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md` and
     `docs/openspec-engineering-loop-harness.md`.
  - **(B28) PR-REVIEW STABILITY — NO SQUASH AFTER REVIEWER ENGAGEMENT; gh-DRIVEN COMMENT RESOLUTION.**
     Two rules that protect a human reviewer's incremental diff once a branch is live as a PR:
       1. **(B28a) No squash on an engaged PR.** `squash-commits`, `loop-finish`, and
          `openspec-redeliver` MUST refuse (fail closed) when the current branch is the head of a
          PR that already has **reviewer engagement** — defined as `gh pr view` reporting
          `comments > 0` OR `reviews > 0` OR at least one non-dismissed review thread. Squashing +
          force-pushing rewrites history and forces the reviewer to re-read every file, so after
          engagement all corrections land as **NORMAL (non-squashed) Conventional commits** on the
          PR branch, pushed normally (no `--force`, no squash). The guard is **fail-open on `gh`
          absence**: if `gh`/token is unavailable the squash proceeds (we never silently block a
          local squash for lack of network); it only blocks when `gh` confirms an engaged PR.
       2. **(B28b) gh-driven PR resolution mode.** When the human/agent prompt says "go to the PR
          for `<branch>`" (or "resolve the PR comments" / "address the review"), the agent MUST run
          `make pr-resolve BRANCH=<branch>` (→ `scripts/pr_resolve.sh`), which uses the `gh` CLI to
          fetch + print the PR's comments and review threads. The agent then follows each comment
          **strictly**, makes the code fix, commits it as a **NORMAL (non-squashed) Conventional
          commit**, and pushes the PR branch **normally** — never `--force`, never squash. The
          script performs NO commit/push itself; it only surfaces the threads for the agent to act
          on. `pr-resolve` and `squash-commits` are mutually exclusive on a reviewed branch.
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md` and
     `docs/openspec-engineering-loop-harness.md`.
  - **(B29) TWO-WAY PR INTERACTION — COMMENT THE FIX + COMMIT ON GREEN GATE.** Extends B28 with
     agent→participant signalling so a human reviewer can resolve threads:
       1. **(B29a) Comment the fix.** After the agent applies a code fix for a PR comment/review
          thread, it MUST post a PR comment (via `make pr-comment BRANCH=<b> BODY=<text>` →
          `scripts/pr_comment.sh`, which calls `gh pr comment`) summarizing the fix and linking the
          fixing commit sha — e.g. `Fixed in <sha>: <one-line summary> — resolves <comment>.` This
          gives the participant a visible, resolvable signal on the PR (they no longer must diff the
          branch to discover what changed).
       2. **(B29b) Commit on green gate (no squash).** When resolving an open PR's comments, the agent
          runs `make loop-harness` (B20 pre-flight); when it is GREEN it commits the fix(es) as
          **NORMAL (non-squashed) Conventional commits** and pushes the PR branch **normally** (no
          `--force`, no squash). This is B27 "deliver on completion" applied to an already-open PR:
          completion = gate green + tasks ticked + hook pass → commit + push. B28a still forbids
          squashing an engaged PR.
       3. **(B29c) Never self-resolve/approve.** The agent posts the fix comment and leaves the thread
          for the human participant to resolve/approve; it does NOT click "Resolve" on the reviewer's
          behalf, and it does NOT approve its own PR.
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md` and
     `docs/openspec-engineering-loop-harness.md`.
  - **(B30) NEVER REVERT — SQUASH ONLY PRE-PR.** A standing, non-negotiable git-history rule
     (user correction):
       1. **(B30a) Reverting commits is NEVER allowed — on ANY branch, especially a PR branch.** The
          agent MUST NOT run `git revert` (nor `git reset`, `git rebase -i` squash/fixup, or any
          history-rewriting command) to "undo" committed work. Corrections are ALWAYS made by adding a
          NEW forward NORMAL (non-squashed) commit. This preserves the reviewer's per-commit view of
          what changed and never rewrites visible history.
       2. **(B30b) Squash is ONLY allowed while the change is LOCAL + pre-PR.** `squash-commits` /
          `loop-finish` / `openspec-redeliver` may squash ONLY when the branch is not yet an open PR.
          The Makefile `squash-commits` guard now refuses (fail-closed, B30) when `gh pr view` reports
          an open PR for the branch OR the branch already tracks a pushed remote — once pushed, squash
          would rewrite public history and is forbidden (this extends B28a from "engaged PR" to "any
          open/pushed PR").
       3. **(B30c) Red gate → forward fix, never revert.** If `make loop-harness` is RED after the
          branch was already pushed / is an open PR, the agent adds a NORMAL forward fixup commit (and a
          PR comment per B29a if resolving a review thread) — it NEVER reverts/rewrites the pushed
          history to "undo" the work.
       4. **(B30d) Explicit override flag.** `make squash-commits ALLOW_SQUASH=1` lets the human
          deliberately bypass the B28a/B30b guard (e.g. an agreed pre-merge cleanup). It is OFF by
          default and ALWAYS prints a loud WARNING that history is being rewritten on explicit request.
          It does NOT bypass B30a (revert is never allowed). Use only when the user explicitly asks.
  - **(B31) MAKE-THROUGH-DOCKER IS ALWAYS A BACKGROUND PROCESS — NEVER THE FOREGROUND SANDBOX.** Every Makefile target that invokes a container runtime (any `docker`, `nerdctl`, or `*compose*` binary via `$(call docker_run, …)`) MUST be executed through the Hermes `terminal(background=true)` channel, which runs on the **real host** that owns the docker/nerdctl daemon and the live Ollama. The foreground sandbox (`/workspace`) has NO container runtime and MUST NOT be used for these targets. This is mandatory for ANY such target — not merely the long-running ones (run-agentics, build-app, test-app, loop-harness, loop-e2e, deliver-change, phase7-archive, release-flow) but also short ones (loop-collect, loop-ts-floor, loop-unit, test-agents-unit, test-agents-integration, verify-agentics-after-run).
    1. **The host is the only supported docker path.** The foreground sandbox returns `docker: command not found` — that is EXPECTED and is NOT a blocker; the host has the daemon. The agent MUST route the target through `terminal(background=true)` and MUST NOT report "can't run from here" / "environment absent".
    2. **No silent foreground runs.** A `make <docker-backed-target>` issued from the foreground terminal is re-dispatched to the background host; the agent never lets it fail on a missing daemon in the sandbox.
    3. **B8 sync.** This behaviour is recorded in the B8 doc-sync set (AGENTS.md, `hermes/skills/openspec-loop-harness.md`, `docs/openspec-engineering-loop-harness.md`, `Makefile`, `scripts/run-loop-harness.sh`) with the B-range string `B1–B34` so `check-docs-sync` stays green.
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md` and `docs/openspec-engineering-loop-harness.md` (B8).
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md` and
     `docs/openspec-engineering-loop-harness.md`.
  - **(B32) `loop-final` — REVIEW-APPROVED SQUASH + CHANGELOG + FORCE-PUSH (the sanctioned exit from
     B28a/B30b).** B28a/B30b forbid the agent from squashing/force-pushing an open PR *on its own
     initiative*; that default STANDS. B32 adds the ONE sanctioned exception: once a human has
     REVIEWED the open PR and EXPLICITLY APPROVES it (an approval phrase such as "PR looks great",
     "looks good", or "approved to finalize"), the agent MAY finalise it with `make loop-final
     BRANCH=<feat/...> APPROVED=1`, which:
       1. **(B32a) Human-approval gate.** Fails closed unless `APPROVED=1` is set. The agent sets it
          ONLY in direct response to a human approval phrase — never in automation, never on its own.
       2. **(B32b) Fresh green loop-harness BEFORE any rewrite.** `loop-final` runs a FRESH
          `make loop-harness` FIRST and ABORTS (no squash, no force-push) if any stage is not green.
          History is NEVER rewritten on a red gate (B30c still holds: a red pushed branch gets a
          forward fix, not a rewrite).
       3. **(B32c) Squash + changelog on green.** On green it runs `squash-commits` (via the B30d
          `ALLOW_SQUASH=1` sanctioned override) → `changelog` → `bump-from-changelog` →
          `changelog-format`, so the CHANGELOG is regenerated from the single squashed typed commit.
       4. **(B32d) `--force-with-lease` to the feature branch ONLY.** The force-push targets the
          feature branch and REFUSES `main`/`origin/main`. Force is `--force-with-lease` only.
       5. **(B32e) B30a stays absolute.** `git revert` (and any "undo committed work" rewrite outside
          this approved squash) is STILL never allowed. `loop-final` is a forward finalisation, not a
          revert.
     Rationale: while review is in progress the reviewer needs a stable incremental diff (B28a/B30b);
     once they have approved, the owner wants tidy single-commit history for merge. `loop-final` is
     the human-gated, gate-verified bridge between those two states. (B31 is the concurrent
     `make-always-background` change / PR #58; this behaviour is B32.)
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md` and
     `docs/openspec-engineering-loop-harness.md`.
  - **(B33) RELEASE PACKAGING IS A HERMETIC, NO-PUBLISH DOCKER+MAKE LOOP GATE.** The release
     artifact set MUST be verified on every loop run WITHOUT calling the GitHub release API. The
     gate `make loop-release-dryrun` runs through docker + make: it builds the plugin (`make
     build-app`, the `containers/npm` node image where rollup + its plugins are installed),
     runs the plugin jest tests (`make test-app`), then runs `scripts/release.sh` in `DRY_RUN=1`
     and ASSERTS the produced `<REPO_NAME>-<TAG>.zip` contains the compiled `main.js` (and that
     `release/main.js` is non-empty). The loop MUST NOT go green while that gate fails. This is
     the regression guard for the 0.4.16 defect (a published release whose zip shipped without
     the compiled plugin). `scripts/release.sh` is PACKAGING-ONLY — it assumes `dist/main.js`
     already exists (built by `make build-app`) and must NOT rebuild inline; `make release`
     depends on `build-app` so the plugin is always compiled before packaging. No GitHub API
     call happens in the loop gate (B14). The `release.yml` CI workflow still publishes on merge
     to main; this gate only proves, locally and hermetically, that the packaging would be valid.
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md` and
     `docs/openspec-engineering-loop-harness.md`.
  - **(B34) NO MERGE / NO FORCE-PUSH UNTIL THE HUMAN APPROVES VIA A PR COMMENT.** A PR opened by
     the agent (delivery of an OpenSpec change) MUST NOT be merged, squashed, or force-pushed by
     the agent until the human has EXPLICITLY approved it through a comment on that PR (e.g.
     "approved", "lgtm", "merge it"). The agent opens/redelivers the PR, then WAITS for the
     approval comment; it must not auto-merge on "green" alone (this overrides the older
     auto-promote-on-green behaviour). This is the standing review gate: the human holds the
     merge decision. B32's `loop-final APPROVED=1` is the ONLY sanctioned finalisation and still
     requires an explicit human approval phrase first.
     B8 sync: mirrored in `hermes/skills/openspec-loop-harness.md` and
     `docs/openspec-engineering-loop-harness.md`.
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
  - **(B12) Delivery gap — verified worktree TS MUST reach the target branch as the PR (on EXPLICIT
    human delivery instruction; see B27).** The pipeline generates + verifies TS **inside a git
    worktree** (`worktrees/<name>`, branch `wt/<name>` by default). The harness MUST NOT stop at a
    green sandbox and LOSE the work — but delivery is the **explicit** human-triggered promotion
    (B27): when the human says "make the PR", the agent promotes `wt/<name>` → `feat/<name>` and
    delivers by **pushing the worktree branch as the PR** (`git push origin feat/<name>`, or
    `make openspec-flow NAME=<name> PUSH=1`) — it MUST NOT copy generated TS back into the parent
    working tree (that would re-introduce pollution; ALL artifacts stay in the worktree by design —
    see `openspec-change-worktree-flow`).
    Corrections redeliver via `make openspec-redeliver NAME=<name>` (`git push --force-with-lease`
    to the SAME PR branch only; never `main`). Never declare a change "done" while its worktree
    branch (`feat/<name>`) has not been delivered. (Earlier wording told the agent to
    `make deliver-change` — a file copy onto the current branch — which conflicts with the
    worktree-confinement invariant; this override supersedes it.)
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

- **The B8 sync docs are ONE source of truth — never let them drift.** The loop/harness
  discipline is defined identically across these sync'd files, and any edit to one MUST be
  mirrored in the others (this is B8). They are enforced by `make check-docs-sync` (the FINAL
  loop stage, `scripts/check-docs-sync.py`), which fails the loop if any disagree on the
  stage order, the `loop-ts-floor` guard, or the B-behaviour range:
  1. **`Makefile`** — the executable gates + canonical stage-order comment; `make loop-harness`
     runs `loop-collect` → `loop-ts-floor` → `loop-unit` → `loop-unit-real` → `loop-e2e`
           → `loop-integration` → `loop-build-app` → `loop-test-app` → `loop-release-dryrun` → `loop-release-tests` → `loop-secret-scan-tests` → `check-docs-sync` (final).
  2. **`AGENTS.md`** — this file: the authoritative narrative + the B1–B34 durable behaviours.
  3. **`hermes/skills/openspec-loop-harness.md`** — the loadable skill mirror of AGENTS.md.
  4. **`docs/openspec-engineering-loop-harness.md`** — the human-readable technical reference
     (named by B8 itself as authoritative; MUST be kept in the sync set, not treated as a 4th
     afterthought — a drift there is what `check-docs-sync` now catches).
  5. **`scripts/run-loop-harness.sh`** — the loop runner: `STAGES` array + canonical stage-order
     comment; the single source of truth for stage execution order.
  6. **The e2e harness** `agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py`
     + the 3 standing e2e gates (`test_ticket20_*` / `test_ticket22_*` / `test_greetings_*`, all
     marked `@pytest.mark.e2e`) — the runtime proof the loop works.
  Before claiming "the loop is green / aligned", run `make check-docs-sync` (the final loop stage)
  and confirm it PASSES: all sync docs agree on the 11-stage order (loop-collect → loop-ts-floor →
  loop-unit → loop-unit-real → loop-e2e → loop-integration → loop-build-app → loop-test-app →
  loop-release-tests → loop-secret-scan-tests → check-docs-sync), the `loop-ts-floor` guard, the B1–B34 behaviours, and
  the live-test skip rule (`OLLAMA_HOST` only, not `GITHUB_TOKEN`). A change is NOT done while any
  of the sync docs disagree.
  - **(B17a) ROOT `tests/` FOLDER IS PART OF THE LOOP.** Beyond `agents/agentics/tests/` (unit /
    integration / e2e) and `tests/test_secret_scanner*.py`, the loop gate ALSO exercises the
    repository-root `tests/` folder through the `loop-release-tests` stage (runs
    `tests/test_release_pipeline_dryrun.py` and any `tests/test_*.py` dry-run harnesses inside the
    `unit-test-agents` container, with `DRY_RUN=1` so no GitHub/network call is made). The
    `check-docs-sync` gate and the canonical stage order MUST list `loop-release-tests` so the root
    `tests/` folder is never silently excluded from the gate.
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
- **Request intake gate (front door) — turn inbound requests into OpenSpec changes before acting.**
  Before implementing/answering a new work request, convert it into an OpenSpec change of record
  (`make openspec-new NAME=<derived>`, which shells out to `openspec new change` per B15) +
  tasks, validate it, and **start the worktree flow** — according to the **per-channel trigger**:
  - **Hermes dashboard:** ALWAYS converts by default — no keyword required.
  - **Telegram:** converts / creates tasks / starts the flow ONLY IF the message contains the
    keyword `openspec` (case-insensitive). Messages without `openspec` are exempt.
  - **Hermes terminal CLI:** converts / creates tasks / starts the flow ONLY IF the command/text
    contains `openspec` (case-insensitive). Requests without `openspec` are exempt.
  After the change validates, the agent runs `make openspec-flow NAME=<name>` (or
  `scripts/openspec-change-flow.sh --name <name>`), which creates a dedicated worktree
  `feat/<name>`, scaffolds the change INSIDE it, generates + runs the loop gate inside it, archives
  on green, finalizes (squash in the worktree), and — with PUSH=1/`--push` — delivers by pushing
  `feat/<name>` as the PR. ALL artifacts stay in the worktree; the parent working tree is NEVER
  touched (B12 override: deliver = PR push, never a file copy). Corrections →
  `make openspec-redeliver NAME=<name>` (force-pushes to the SAME PR branch).
  Degenerate cases: re-use an in-flight change for the same intent (no duplicate dir); use
  `clarify` first if ambiguous.
  **Kanban-delivery path:** when a request arrives AS a Kanban task (assigned into a kanban
  workspace, agent scoped to that task), the Kanban wrapper is only the *delivery envelope* —
  the agent MUST still apply the per-channel trigger and scaffold the OpenSpec change via
  `make openspec-new` / `openspec new change`; do NOT limit itself to kanban tooling.  The reusable directive lives in the Hermes skill
  `request-to-openspec` (loaded at request entry). Mirrored in `openspec-loop-harness.md` and
  `docs/openspec-engineering-loop-harness.md` (B8).

---

## Secret scanning (gitleaks)

The broken TruffleHog GitHub Action was replaced by **gitleaks** (the de-facto open-source scanner).
The actual secret **scan** lives in the pre-commit hook + CI (NOT a loop-harness stage); the
secret-scanner's own **pytest suite** runs as a loop-harness stage (`loop-secret-scan-tests`).

- **Engine:** `scripts/secret_scanner.py` delegates 100% of detection to gitleaks — no homemade
  regex/entropy detector. It is the LOCAL fail-closed **hook** guard (dev-side), not a loop command.
- **Config:** `.gitleaks.toml` uses `[extend] useDefault = true` plus repo-local `allowlist` entries
  for test fixtures, docs, dependency/build caches (`.venv`, `node_modules`, `__pycache__`, and so on),
  and `.env`/`.git`. **Do NOT replace `useDefault = true` with an empty `path`** — that silently
  disables the entire default ruleset.
- **Scan lives in the hook + CI (NOT the loop):** the gitleaks repo scan runs in `git-hooks/pre-commit`
  (`python3 scripts/secret_scanner.py --staged`) and `git-hooks/commit-msg` (`--message-file`), and in
  CI (`.github/workflows/trufflehog.yml`, `gitleaks/gitleaks-action@v2`). A detected secret blocks the
  commit / fails CI. A standalone `make loop-secret-scan` target exists for on-demand scans but is NOT
  a loop stage (the loop must not re-scan the tree — the hook already guards every commit).
- **Loop stage = the scanner's own tests (containerized, B9):** `make loop-secret-scan-tests` builds
  `secret-scan-tests-image` (real gitleaks + pytest) and runs `tests/test_secret_scanner*.py` **inside
  the `gitleaks-tests` compose container** (`docker-compose-files/gitleaks-tests.yaml`), exercising the
  REAL gitleaks binary (no mocks on detection). It sits between `loop-test-app` and `check-docs-sync`
  in the canonical stage order. This verifies the scanner's detection logic itself every loop run.
- **No duplicate scan commands:** the Makefile has exactly ONE on-demand scan target (`loop-secret-scan`,
  alias `check-secrets`); it does NOT shell out to `python3` or a bare host `gitleaks` binary — docker
  compose only, like every other harness gate. `make secret-scan-image` / `make secret-scan-tests-image`
  build images; `make test-secret-scanner` runs the pytest suites on the host. `loop-secret-scan-tests`
  is the canonical loop entry that runs the suite containerized.
- **Hooks (fail-closed, local dev guard):** `git-hooks/pre-commit` runs `python3 scripts/secret_scanner.py --staged`;
  `git-hooks/commit-msg` runs `python3 scripts/secret_scanner.py --message-file`. A detected secret
  rejects the commit. Installed via `make install-git-hooks`.
- **CI:** `.github/workflows/trufflehog.yml` is a gitleaks workflow (`gitleaks/gitleaks-action@v2`,
  `fetch-depth: 0`, `GITLEAKS_CONFIG=.gitleaks.toml`).
- **Tests:** `tests/test_secret_scanner.py` (hermetic unit) + `tests/test_secret_scanner_integration.py`
  (real gitleaks binary, no mocks on detection). Run with `make test-secret-scanner` (host) or via the
  loop stage `loop-secret-scan-tests` (containerized).
- **Credential hygiene:** never put real API keys/tokens in source or tests. Use documented example
  shapes (e.g. `AKIA…EXAMPLE`, `xoxb-…`) or `[REDACTED]`.
