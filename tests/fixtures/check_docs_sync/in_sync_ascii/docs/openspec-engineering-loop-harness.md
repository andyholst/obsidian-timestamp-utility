# OpenSpec Engineering‑Loop Harness — Technical Reference

> **What this document is.** A complete, human‑readable technical description of how
> `obsidian-timestamp-utility` turns an OpenSpec change into working TypeScript and
> verifies it. It covers the three layers that make the system work:
>
> 1. **OpenSpec behaviour** — the spec‑driven source of truth and its CLI workflow.
> 2. **Harness engineering** — the Python "agentics" pipeline (`agents/agentics/`) and
>    the deterministic merge floor that writes your `src/main.ts` / `src/__tests__/main.test.ts`.
> 3. **Loop engineering** — the bounded self‑correcting build→test→fix loop and the
>    durable behaviours **B1–B26** that the loop must always honour.
>
> It also documents the **file structure**, every file that creates the harness's
> behaviour, and a **how‑to‑use** walkthrough for authoring a new feature.

This is the authoritative guide. Older references (`new-loop-harness-open-spec-engineering-loop.md`
at repo root, the previous `docs/openspec-loop-harness-guide.md`) are historical / redirect stubs.

---

## 0. Fundamentals — what "harness" and "loop" engineering mean

Before the technical detail, understand the two disciplines this whole system is built on.
Everything below (OpenSpec, the Python pipeline, the Makefile, B1–B26) is just a concrete
implementation of these two ideas. If you internalise this section, the rest of the document
reads as "here is *how* we do harness + loop engineering in this repo."

### 0.1 The core problem

An LLM is a **non‑deterministic generator**. Ask it to write the same feature twice and you get
two different files — sometimes correct, sometimes subtly broken, sometimes missing code it wrote
last time. You cannot ship software by trusting raw LLM output directly, because:

- it drifts (near‑misses: `insert-random-id` instead of the spec's `insert-uuid-v7`),
- it omits (drops existing logic when regenerating a file),
- it hallucinates (imports, APIs, test bodies that don't exist),
- it is unrepeatable (no two runs are identical).

**Harness engineering** and **loop engineering** are the two complementary answers to this
problem. One *constrains* the generator; the other *corrects* it. Together they turn an
unreliable generator into a dependable, spec‑driven build system.

### 0.2 What harness engineering is

A **harness** is the deterministic scaffolding that surrounds a non‑deterministic component
(here, the LLM) and forces its output into a known‑good, verifiable shape. It is the "jig" a
machinist clamps a part into so every cut lands in the same place regardless of who is holding
the tool.

Harness engineering means designing that scaffolding so that:

- **There is a single source of truth.** The *intent* lives in one authoritative place (here,
  the OpenSpec change — `tasks.md` `## Contract` / `## Test Contract`), never scattered across
  prompts or hard‑coded in glue code (behaviour **B10**).
- **The generator never holds the pen.** The LLM proposes; a **deterministic assembler** decides
  what actually gets written. In this repo the `CodeIntegratorAgent` string‑merge floor is the
  *sole* writer of `src/main.ts` — the LLM only produces raw candidate text (behaviours **B7**,
  **B11**). This is the difference between "the AI wrote my file" (fragile) and "the AI proposed
  content that my deterministic floor validated and merged" (robust).
- **Output is bounded and checkable.** The harness knows the exact contract (command id, name,
  Modal class) and can *guarantee* it is present (idempotent injection), *guarantee* nothing was
  dropped (the omission guard), and *guarantee* the workspace is reset to a known baseline
  afterward (git‑HEAD restore, B5/B6).
- **Everything runs the same way every time.** One execution path (`docker compose` via the
  Makefile), pinned dependencies (`requirements.in` → generated `requirements.txt`), enforced
  permissions (the B9 floor). Reproducibility is a harness property, not luck.

In short: **the harness makes an unreliable generator produce reliable artifacts** by clamping
its output to a spec and owning the write/verify/reset machinery around it.

### 0.3 What loop engineering is

A harness makes a *single* generation trustworthy. But the first attempt often still fails
(a type error, a failing test, an under‑delivered contract). **Loop engineering** is the
discipline of building a **closed feedback loop** that detects that failure and drives the system
back toward "correct" — automatically, repeatably, and with a hard stop.

A well‑engineered loop has four parts:

1. **Generate** — produce a candidate (run the harness / pipeline).
2. **Verify** — run an *objective* gate that defines "done": here `make build-app` (tsc/rollup
   exit 0) + `make test-app` (jest pass) + a walk of every spec requirement/scenario. The gate is
   the loop's definition of truth — if it's weak, the loop optimises for the wrong thing.
3. **Diagnose & correct** — on failure, change an **input** and try again. The critical rule:
   **fix the source of truth, not the symptom.** Here that means editing the OpenSpec spec/contract,
   restoring the generated files to a clean baseline, and re‑running — *never* hand‑patching the
   generated TS (behaviour **B11**). Each iteration must try a *different* correction, or the loop
   just spins.
4. **Terminate** — a bounded number of attempts (~5 here) and a clear escalation path (fall back
   to fixing the Python floor as a last resort, B13). A loop with no bound is an infinite loop;
   a loop with no escalation hides real defects.

The loop is also where **durability** lives: the invariants that must hold on *every* pass
(B1–B26) — a permanent regression e2e that outlives every feature (B1–B6), the no‑commit/no‑push
gate (B4/B14), the delivery step that moves verified code out of the worktree onto the branch
(B12). These are the loop's "laws of physics": conditions that never regress no matter how many
times you go round.

In short: **loop engineering makes the system self‑correcting and self‑verifying**, so that
"generate once and hope" becomes "generate → prove → fix the spec → repeat until the objective
gate is green, then stop."

### 0.4 How the two fit together

| Discipline | Job | Answers the question | In this repo |
|-----------|-----|----------------------|--------------|
| **Harness engineering** | *Constrain* the generator into a verifiable shape | "How do I make one generation trustworthy?" | OpenSpec contract as source of truth + `CodeIntegratorAgent` deterministic merge floor + omission guard + B9 perms + git‑HEAD restore |
| **Loop engineering** | *Correct* the generator across attempts until an objective gate passes | "How do I make the system converge on correct, and know when to stop?" | `make build-app`/`make test-app` gate + spec‑first self‑correct loop (bounded ~5) + durable behaviours B1–B26 + delivery step B12 |

The harness is the **floor** (nothing worse than this can be written); the loop is the **ratchet**
(each pass can only move toward green, and the invariants never slip back). The rest of this
document is the concrete machinery that implements both.

---

## 1. Mental model (read this first)

The system is a **spec‑driven, self‑correcting code generator**. The flow is:

```
   You write an OpenSpec change  ──►  Python pipeline reads it  ──►  generates TS + tests
   (openspec/changes/<name>/)         (agents/agentics, local)        (src/main.ts + tests)
                                              │                                  │
                                              ▼                                  ▼
                                      Deterministic merge floor        make build-app / make test-app
                                      (spec contract wins)                  │
                                                                            ▼
                                                     self-correct loop: fix SPEC → restore → re-run
                                                                            │
                                                                            ▼
                                                  green?  archive spec (B1) + deliver TS (B12)
                                                  (you decide commit/push — B4)
```

Three non‑negotiable principles:

- **The OpenSpec change is the single source of truth.** The generated TypeScript body
  lives *only* in the change's `tasks.md` (`## Contract` / `## Test Contract` blocks), never
  in Python string literals (behaviour **B10**).
- **The pipeline never hands the LLM the file‑writing pen.** A deterministic string‑merge
  floor (`CodeIntegratorAgent`) is the *sole* writer of generated TS (behaviour **B11**).
- **The agent never commits or pushes.** Saving the result is a deliberate human step
  (behaviours **B4**, **B14**).

---

## 2. File structure (what creates the behaviour)

```
obsidian-timestamp-utility/
├── AGENTS.md                         # Repo‑level authority: phase flow + B1–B26 summary
├── Makefile                          # ALL execution entry points (docker compose only, no Dagger)
├── docker-compose-files/
│   ├── agents.yaml                   # agentics / unit‑test‑agents / integration‑test‑agents services
│   ├── tools.yaml                    # `app` = npm/rollup/jest build+test container
│   └── pip.yaml                      # pip‑compile image → regenerates requirements.txt
├── containers/
│   ├── agents/Dockerfile             # Python agentic runtime (Ollama client, pytest, etc.)
│   ├── npm/Dockerfile                # Node build/test runtime
│   └── pip/Dockerfile                # pip‑compile runtime
├── docker-files/
│   └── pip-requirements/
│       └── requirements.in          # SINGLE source for Python deps (compile → requirements.txt)
├── openspec/                        # ◀── the spec‑driven source of truth
│   ├── changes/
│   │   ├── <name>/                   # an ACTIVE change
│   │   │   ├── proposal.md           # Why / What / Capabilities / Impact
│   │   │   ├── tasks.md              # checkbox plan + ## Contract + ## Test Contract (the spec TS)
│   │   │   ├── design.md             # optional design notes
│   │   │   └── specs/<cap>/spec.md   # delta‑format requirements + scenarios
│   │   └── archive/<date>-<name>/    # archived (merged) changes — spec only
│   └── specs/<cap>/spec.md           # merged capability specs (after archive)
├── agents/agentics/                  # ◀── the HARNESS ENGINE (the Python pipeline)
│   ├── src/
│   │   ├── agentics.py               # LangGraph entry point; assembles the agent graph
│   │   ├── openspec_loader.py        # load_change(): change → synthetic GitHub‑issue shape
│   │   ├── fetch_issue_agent.py      # falls back to openspec_loader for local change refs
│   │   ├── code_generator_agent.py   # LLM → raw TS code
│   │   ├── test_generator_agent.py   # LLM → raw TS tests
│   │   ├── code_integrator_agent.py  # ◀── THE DETERMINISTIC MERGE FLOOR (writes src/main.ts)
│   │   ├── pre_test_runner_agent.py  # runs jest/tsc before integration (gates)
│   │   ├── post_test_runner_agent.py # runs jest/tsc after integration (verdict)
│   │   ├── error_recovery_agent.py   # bounded re‑run loop on failure
│   │   ├── code_extractor_agent.py   # pulls fenced ```ts blocks out of LLM text
│   │   └── ... (30+ support modules: tools, prompts, state, workflows, monitoring…)
│   ├── tests/
│   │   ├── unit/                     # real‑logic unit tests (mocks only external calls)
│   │   └── integration/
│   │       ├── test_change_driven_ts_generation_e2e.py  # ◀── PERSISTENT e2e harness (B1)
│   │       ├── _e2e_helpers.py       # run_pipeline_isolated() — B3 isolated temp‑dir runner
│   │       └── conftest.py
│   └── requirements.txt              # GENERATED by `make generate-requirements` (never hand‑edit)
├── src/
│   ├── main.ts                       # ◀── the real plugin; what the pipeline generates/integrates
│   └── __tests__/main.test.ts        # ◀── the real plugin tests the pipeline generates/integrates
├── backups/                          # timestamped pre‑generation copies of src/main.ts etc. (git‑ignored)
├── worktrees/                        # git worktrees where generation+verify happens in isolation
├── agent-wiki/                       # YYYY‑MM‑DD‑<name>.md per‑change work records
└── hermes/skills/openspec-loop-harness.md   # skill mirror of AGENTS.md (B8: keep in sync)
```

**Behaviour‑creating files at a glance**

| File | Role in the harness |
|------|---------------------|
| `Makefile` (`run-agentics`, `build-app`, `test-app`, `b9-perms`, `phase7-archive`, `deliver-change`) | Orchestrates everything via docker compose; implements the omission guard + B9 perms floor + B4 no‑commit gate. |
| `openspec/changes/<name>/tasks.md` | The executable plan **and** the authoritative TS contract (`## Contract`, `## Test Contract`). |
| `agents/agentics/src/openspec_loader.py` | Turns a local change into the synthetic issue the pipeline expects. |
| `agents/agentics/src/code_integrator_agent.py` | **The merge floor.** Parses the spec contract and deterministically injects it into `src/main.ts` + tests. |
| `test_change_driven_ts_generation_e2e.py` + `_e2e_helpers.py` | The permanent regression guard (B1–B6). Always runnable, isolated, restores repo to git HEAD. |
| `AGENTS.md` / `hermes/skills/openspec-loop-harness.md` | The two mirrored sources of truth for the whole behaviour set (B8). |

---

## 3. OpenSpec behaviour (the spec‑driven source of truth)

### 3.1 The change folder

A change is a directory under `openspec/changes/<kebab-name>/`. It contains:

- **`proposal.md`** — *Why* / *What Changes* / *Capabilities* / *Impact*.
- **`specs/<capability>/spec.md`** — the capability spec in **delta format** the CLI validates:
  ```markdown
  ## ADDED Requirements
  ### Requirement: <name>
  The system MUST <text>.
  #### Scenario: <name>
  - **WHEN** <condition>
  - **THEN** <outcome>
  ```
- **`tasks.md`** — a checkbox execution plan (`- [ ] X.Y ...`) **plus** the authoritative
  TypeScript contract. This is the file the pipeline reads to know what to build.
- **`design.md`** — optional design rationale.

The canonical real example is `openspec/changes/uuid-modal-agentic-generation/` (an Obsidian
"Insert UUID v7" command implemented as a `UuidV7Modal` registered via `addCommand`).

### 3.2 The contract blocks (where generated TS actually lives)

Inside `tasks.md`, two fenced blocks hold the **exact** TypeScript the integrator must emit.
These are the ONLY place generated TS bodies are allowed to exist (behaviour **B10**).

**`## Contract`** — contains one or more fenced ```ts blocks delimited by markers:

```ts
// === CONTRACT_COMMAND === (injected inside onload())
this.addCommand({ id: 'insert-uuid-v7', name: 'Insert UUID v7 (timestamp-based)', … });
// === CONTRACT_GENERATOR === (injected inside TimestampPlugin)
generateUuidV7(): string { … }
// === CONTRACT_MODAL === (injected as a top-level module member)
export class UuidV7Modal extends obsidian.Modal { … }
// === END_CONTRACT ===
```

**`## Test Contract`** — contains the regression tests, delimited by
`=== TEST_CONTRACT_* ===` / `=== END_TEST_CONTRACT ===` markers. These assert the exact
contract (command id, name, v7‑regex, Notice‑on‑no‑editor). The integrator injects them
verbatim and *discards* any hallucinated LLM test blocks (behaviour **B11**).

### 3.3 How the change directory is actually created (the CLI, not magic)

Newcomers often ask: *"where does `openspec/changes/<name>/` actually come from?"* The answer
is the OpenSpec CLI — **not** the agentic Python code, not a hand-built directory tree. The CLI
is the single, authoritative scaffolder:

```bash
# From the repo root. This creates the change directory + tracks it in .openspec.yaml.
openspec new change <kebab-name>

# Inspect the exact templates the CLI expects before you fill them in:
openspec instructions proposal --change <kebab-name>
openspec instructions tasks    --change <kebab-name>

# Gate before any implementation happens:
openspec validate <kebab-name>            # proposal + delta specs + tasks must parse
openspec status  --change <kebab-name>    # artifact completion (proposal / tasks / specs)

# Archive only the SPEC (merge specs/** into openspec/specs/); never touches generated TS or git:
openspec archive <kebab-name>
```

What `openspec new change <kebab-name>` produces on disk:

```
openspec/changes/<kebab-name>/
├── .openspec.yaml          # change metadata (the CLI writes this)
├── proposal.md             # YOU author: Why / What Changes / Capabilities / Impact
├── specs/<kebab-name>/     # YOU author: spec.md in delta format (## ADDED Requirements)
│   └── spec.md
├── tasks.md                # YOU author: checkbox plan + ## Contract / ## Test Contract TS
└── design.md               # optional design rationale
```

The CLI creates the **directory + `.openspec.yaml`** and validates your authored content. It does
**not** write `proposal.md` / `specs/.../spec.md` / `tasks.md` bodies for you — those are the
human/agent-authored source of truth. (In the rare case where the CLI version emits no
`proposal.md`/`tasks.md`, the agent still authors them by hand under the scaffolded path — the
directory shape above is the contract `openspec validate` checks against.)

**GitHub ticket → local OpenSpec change (how the pipeline seeds it).** When a change is driven by
a GitHub issue rather than a pre-existing local change, the agentic code **reuses this exact CLI
flow** at runtime instead of hand-writing directories:

1. `fetch_issue_agent.py` fetches the issue once (live GitHub, requires `GITHUB_TOKEN`).
2. It calls `openspec_loader.create_change_from_issue(url, title, body)` — which **shells out to
   `openspec new change ticket<N>`** to scaffold the change directory (same CLI step a human
   runs), then writes `proposal.md` / `specs/<cap>/spec.md` / `tasks.md` derived from the issue.
3. It then re-points `state["url"]` to `openspec:ticket<N>` and `load_change` reads the **local**
   change. From that point on, generation runs **entirely offline** — no further GitHub calls.

This is the bridge to a stable, repeatable e2e workflow: the live fetch happens once, the result
is mirrored as a local OpenSpec change (single source of truth), and every subsequent run —
including the `ticket20`/`ticket22` e2e tests — regenerates that change via the CLI and runs
locally. Re-running on the same issue is idempotent (the change is reused if it already exists),
so the tests are deterministic and never depend on network flakiness.

| Command | Purpose |
|---------|---------|
| `openspec new change <kebab>` | Scaffold `openspec/changes/<kebab>/` with `.openspec.yaml` (the directory creation step). |
| `openspec instructions proposal --change <name>` | Print the exact proposal template. |
| `openspec instructions tasks --change <name>` | Print the exact tasks template. |
| `openspec validate <name>` | Validate `proposal.md` + delta `specs/**` + `tasks.md`. **Must pass before implementation.** |
| `openspec status --change <name>` | Show artifact completion (proposal / tasks / specs). |
| `openspec archive <name>` | Merge `specs/**` into `openspec/specs/` (spec only; no TS, no git). |

> **Spec always wins.** If generated code and the contract disagree, the contract (spec) is
> right. The pipeline's job is to honour the spec, not to invent its own version
> (behaviours **B7**, **B11**).

---

## 4. Harness engineering (the Python pipeline)

### 4.1 Entry & local‑change loading

`make run-agentics CHANGE=<name>` runs (inside the `agentics` container):

```
python -m prod.agentics openspec:<name>
```

`agentics.py` builds the LangGraph agent graph. The pipeline was originally designed to
consume a **GitHub issue URL**; for local OpenSpec‑driven runs it is fed a *synthetic* issue:

- `openspec_loader.load_change(change_name)` reads `proposal.md` + `tasks.md` + `specs/**`,
  synthesizes a GitHub‑issue‑shaped `ticket_content` (Description / Specifications / Design /
  Tasks), and returns `url = "openspec:<name>"`.
- `FetchIssueAgent.process` detects a local change ref (`is_local_change_ref`) and calls the
  loader instead of hitting GitHub. No `GITHUB_TOKEN` is required for generation. **No MCP
  server is used** — execution is docker‑compose only (behaviour in the skill: *No Dagger, no
  MCP*).

### 4.2 The agent graph (high level)

```
FetchIssueAgent ──► TicketClarityAgent ──► ImplementationPlannerAgent
        │
        ├──► CodeExtractorAgent ──► CodeGeneratorAgent ──► (raw TS code)
        ├──► TestGeneratorAgent ──► (raw TS tests)
        │
        └──► CodeIntegratorAgent  ◀── the deterministic merge floor (writes src/main.ts)
                    │
                    ├── PreTestRunnerAgent  (build/test gates BEFORE/AROUND integration)
                    └── PostTestRunnerAgent (build/test verdict AFTER integration)
                                │
                                └── (on failure) ErrorRecoveryAgent ──► re‑run generator+integrator (bounded)
```

Key point: **the LLM agents produce *raw* code/test text only.** They are *not* given the
`write_file_tool` for generated TS (behaviour **B11**). The `CodeIntegratorAgent` is the sole
writer of `src/main.ts` and `src/__tests__/main.test.ts`.

### 4.3 The deterministic merge floor (`CodeIntegratorAgent`)

This is the heart of the harness. It guarantees the spec contract is always present in the
generated files, regardless of how variable the LLM's raw output is.

**Step A — canonical file forcing.** Even if the LLM forgets to flag them, the integrator
forces `src/main.ts` and `src/__tests__/main.test.ts` into the relevant‑files lists so the
merge floor always processes the real plugin entrypoint (never a stray derived filename).

**Step B — contract parsing (`_expected_contract_for_change`).** Reads the change's
`specs/<name>/spec.md` and `tasks.md` and parses:

- `command_id` (`id: 'insert-uuid-v7'`)
- `command_name` (`name: 'Insert UUID v7 (timestamp-based)'`)
- `modal_class` (`UuidV7Modal`)
- `generator_kind` — **derived from spec text** (`uuid v7` → `uuidv7`), never a hard‑coded string
- `contract_ts` — the verbatim TS between `=== CONTRACT_COMMAND/GENERATOR/MODAL ===` markers
- `test_contract_ts` — the verbatim TS under `## Test Contract`

If nothing is pinned, the change stays free‑form. This is how "`openspec:…`" makes the spec win.

**Step C — assembly (`generate_updated_code_file` → `_assemble_contract_features`).**
A **string‑only, idempotent** merge:

1. Strips any non‑contract `this.addCommand(...)` and any existing/LLM Modal of that name from
   **both** the existing file and the LLM output (so re‑runs never duplicate).
2. Injects the **authoritative** contract command body (exact id/name, calls the spec generator).
3. Appends the spec Modal subclass + spec generator function **only if not already present**.

Anchors used: import insertion at top; `addCommand` injected **inside** `onload()`; Modal/generator
injected just **before** the file's final closing brace (so they are top‑level module members, not
orphans). `_extract_balanced_blocks` is **line‑aware** and consumes the trailing `);` of each
`this.addCommand({...});` block — missing that caused `TS1005: ',' expected` in earlier runs.

**Step D — safety net (`_ensure_contract_present`).** Unconditionally guarantees the contract
pieces are present (string‑checked, idempotent — appends only what's absent). This removes the
per‑run non‑determinism where the command landed but the Modal didn't.

**Omission guard (`generate_updated_code_file`).** If the deterministic merge ever yields output
**smaller** than the existing file, it falls back to an LLM merge — and the Makefile's
`run-agentics` separately re‑checks byte size vs the pre‑run backup (see §5).

### 4.4 Why no TS is hard‑coded in Python (behaviour **B10**)

`code_integrator_agent.py` contains **no** generated TS bodies as string literals — no
`addCommand({...})`, no `class X extends obsidian.Modal {...}`, no `describe(...)`/`it(...)`.
Python only (a) parses the spec markers, (b) performs the deterministic merge at known anchors,
and (c) injects the spec's **verbatim** contract TS. The only spec‑derived tokens allowed in
Python are identifiers used for idempotency guards (e.g. checking `class UuidV7Modal` is present).

Verify with:
```bash
grep -nE "addCommand\(|extends obsidian\.Modal|describe\('|it\('|test\('" agents/agentics/src/*.py
```
It must return **only** comments / docstrings / idempotency‑guard regexes — never TS body literals.

### 4.5 The persistent E2E harness (behaviours **B1–B6**)

`agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py` is the permanent
regression guard. It:

- **B1** — must never be deleted when a change is archived; it outlives every feature.
- **B2** — reads `<repo>/openspec/changes/<CHANGE>/tasks.md` (+ `spec.md`), asserts a
  "generate `<Feature>Modal` registered as a command" task exists, then asserts the generated
  `src/main.ts` contains that `obsidian.Modal` subclass wired via `this.addCommand(...)`. It
  validates against the change's **own** spec, never a hard‑coded expectation.
- **B3** — runs the pipeline into an **isolated temp dir** (`_e2e_helpers.run_pipeline_isolated`
  spawns a subprocess with `PROJECT_ROOT` forced to a temp dir, copying in `src/` + `openspec/`
  + build configs). It never writes generated TS into the repo or the agentics source tree.
  Skips cleanly if `OLLAMA_HOST` is unset.
- **B4** — never calls `git commit/push/add/merge`. A regex self‑check asserts no git op leaked
  into generated output.
- **B5** — restores the repo's real `src/main.ts` / `src/__tests__/main.test.ts` to **git HEAD**
  after every run (via `git show HEAD:<rel>`), so it never leaves uncommitted generated TS behind.
- **B6** — if generated task code already exists on disk, it still runs + re‑generates into the
  isolated temp dir to prove pipeline health, writes nothing back, and restores to git HEAD.

Run it with: `make test-agents-e2e` (`pytest -m e2e`).

---

## 5. Loop engineering (the self‑correcting cycle)

### 5.1 The phase flow

| Phase | What happens | Key command |
|-------|--------------|-------------|
| 0 | Structure already scaffolded (`openspec/`, `containers/`, `worktrees/`, `agent-wiki/`). | — |
| 1 Propose | Create the change; write `proposal.md` + `specs/<cap>/spec.md` (delta). | `openspec new change <name>` |
| 2 Tasks | Write `tasks.md` checkbox plan + `## Contract` + `## Test Contract`. | (edit file) |
| 3 Validate | **Do not implement until this passes.** | `openspec validate <name>`; `openspec status --change <name>` |
| 4 Worktree | Generate inside an isolated git worktree (branch `feat/<name>`). Work ONLY this change's tasks. | `git worktree add ../worktrees/<name> -b feat/<name>` |
| 5 Backup+Generate | Timestamp‑back up `src/main.ts`+`main.test.ts`, then run the pipeline. **Omission guard** auto‑restores if a file shrank. | `make run-agentics CHANGE=<name>` |
| 6 Verify (loop) | `make build-app` (exit 0) → `make test-app` (jest pass). Walk every requirement/scenario. If it fails, **loop** (fix spec → restore → re‑run). Be strict + honest. | `make build-app`; `make test-app` |
| 7 Document+Decide | Write `agent-wiki/YYYY-MM-DD-<name>.md` (Verification Against Spec per requirement + update `index.md`). If green → `openspec archive <name>` (spec only). | `make phase7-archive CHANGE=<name>` |

### 5.2 The self‑correct loop (bounded)

When `make build-app` (`tsc`/`rollup`) or `make test-app` (jest) fails on the generated files,
the harness follows a **fixed, spec‑first** routine (behaviour **B11**):

1. **Fix the OpenSpec change first** — edit `tasks.md` `## Contract` / `## Test Contract`
   (markers, acceptance criteria). The spec is the source of truth; the fix lives **there**.
2. **Restore** the generated files to the timestamped `backups/` snapshot or the last committed
   baseline, so no broken generated code carries over.
3. **Re‑run** `make run-agentics` → `make build-app` + `make test-app` until green.

Repeat up to **~5** full e2e runs. Each failed attempt must try a **different** tweak to the
spec/contract file — never a hand‑edit of the generated TS. Only after ~5 spec‑driven attempts
fail may the agent fall back to editing the **Python agentic code** (integrator / contract parser
/ self‑correct loop) as a last resort; even then the generated TS is never patched by hand.

> **You should never hand‑edit `src/main.ts` / `src/__tests__/main.test.ts` yourself.** That
> breaks the link between the spec and the code. If the *deterministic floor itself* is defective
> (e.g. the integrator skips injecting the contract when the LLM already emitted a same‑named
> block), fix the Python `CodeIntegratorAgent` directly — that is the correct spec‑steered fix
> (behaviour **B13**), not a hand‑edit of generated TS.

### 5.3 The omission guard (Makefile)

`make run-agentics` does, in order:

1. **Backup** — copies the current `src/main.ts` + `src/__tests__/main.test.ts` to
   `backups/<file>.<TIMESTAMP>.bak` (safety net; `backups/` is git‑ignored).
2. **Run** — `docker compose … agentics python -m prod.agentics openspec:<CHANGE>` (plain
   `docker compose run --rm …`; the PTY that nerdctl's forced `--tty` requires is provided by
   the caller — `make loop-harness` wraps `make` in `setsid script`, and a human `make run-agentics`
   already has a real terminal console).
3. **Omission check (contract-aware).** Compares each generated file's byte size against its
   newest backup. A shrink is only a *genuine* omission if the generated file also **dropped the
   spec's contract command id** (parsed from the change's `tasks.md`/`spec.md`). A legitimate
   feature switch (e.g. the greetings test is smaller than the uuid test) produces a
   different-sized file, so pure byte-size comparison is a false positive — if the contract
   command id is present, it is a successful generation and is **never** restored. Only when the
   command id is **MISSING AND the file shrank** does the Makefile auto-restore the backup and
   flag it: you must then investigate why the Python code dropped content (inspect
   `code_integrator` / `code_extractor` / `export_name` assembly) and fix the **root cause**
   before re-running. Never ship a shrunk file.

### 5.3.1 The real agent‑unit gate (`loop-unit-real`, behaviour **B18**)

The mocked unit run (`loop-unit` → `make test-agents-unit-mock`) is fast and hermetic, but it
proves nothing about the agent units running against the **real** LLM. The loop MUST also run
`loop-unit-real` → `make test-agents-unit` (live Ollama; the unit under test is **never** mocked —
only the Ollama/HTTP boundary may be). This is gate 2 of 7 in `make loop-harness` (after the
collection guard at 0 and the mocked gate at 1), immediately after the mocked gate.

- **Run both, report both.** Reporting "agent tests green" after **only** the mocked run is
  INCOMPLETE. State the `loop-unit` (mocked) AND `loop-unit-real` (real) results explicitly.
- **When Ollama is reachable** (the normal case here: the host runs Ollama and the rootless-nerdctl
  containers are host-networked, so `127.0.0.1:11434` from inside a container reaches it — see B19),
  `make test-agents-unit` MUST be run and its pass/fail reported alongside the mocked run. On this
  project Ollama is ALWAYS reachable through `make`, so `loop-unit-real` and `loop-e2e` are EXPECTED
  to RUN, not skip.
- **When Ollama is genuinely unreachable** (e.g. the host Ollama is down and cannot be restarted),
  `loop-unit-real` SKIPS (it must not error) — but the agent MUST say the real unit gate did *not*
  execute, not silently fold it into the mocked run's "green". Do not assume Ollama is absent; the
  host provides it.

### 5.4 The B9 permission floor (rootless nerdctl)

Execution is docker compose with **rootless nerdctl**, which remaps the container uid (1000) to
the host **`other`** class. The `b9-perms` Makefile target is a **prerequisite** of
`run-agentics` / `build-app` / `test-app`, so it runs automatically:

```bash
chmod -R a+rX .                                   # whole repo readable+traversable
chmod -R a+rwX src backups openspec results agent-wiki   # container write targets
```

Skip these and you get `PermissionError: [Errno 13]` mid‑run. Run `make b9-perms` manually only
if invoking docker compose outside the Makefile. World‑readable on a private repo is acceptable.

### 5.5 Delivery gap (behaviour **B12**)

`make run-agentics` generates + verifies TS **inside a worktree**. The harness must NOT stop
there: a feature green only in the worktree that never lands on its target branch is a failed
delivery. Deliver it by **pushing the worktree branch as the PR** — NOT by copying files back into
the parent working tree (that would re-introduce pollution; ALL artifacts stay in the worktree by
design — see `openspec-change-worktree-flow`):

```bash
make openspec-flow NAME=<name> PUSH=1     # creates worktree, archives on green, finalizes, pushes feat/<name> as PR
# corrections after a pass:
make openspec-redeliver NAME=<name>        # re-enters worktree, re-squashes, force-pushes to the SAME PR branch (--force-with-lease, never main)
```

Never declare a change "done" while its worktree branch (`feat/<name>`) has not been delivered.
(The earlier `make deliver-change` file-copy directive conflicts with the worktree-confinement
invariant and is superseded by this PR-push model.)

---

## 6. Durable behaviours B1–B26 (must always hold, never regress)

| ID | Behaviour |
|----|-----------|
| **B1** | Persistent E2E test per generated‑TS change. `test_change_driven_ts_generation_e2e.py` must **never** be removed when a change is archived/done. Archiving merges only the *spec*; the e2e stays forever. |
| **B2** | E2E reads the task file. It loads `tasks.md` (+`spec.md`), confirms a "generate `<Feature>Modal` registered as a command" task, and asserts the generated `src/main.ts` contains that `obsidian.Modal` wired via `this.addCommand(...)`. Validates against the change's own spec, never a hard‑coded expectation. |
| **B3** | E2E generates uniquely + is always runnable. Runs the pipeline into an **isolated temp dir** (unique per run); never touches the real `src/main.ts` or the agentics source tree. Runnable via `make test-agents-e2e`; skips cleanly without a real Ollama. |
| **B4** | **NEVER commit/push** when generated task code already exists. The pipeline + e2e harness must not call `git commit/push/add/merge`. `make run-agentics` / `make phase7-archive` only write/archive TS + spec; committing/pushing is a deliberate, separate human action. |
| **B5** | E2E restores TS files to the **COMMITTED** baseline. After every run, the repo's real `src/main.ts` / `src/__tests__/main.test.ts` are restored to **git HEAD** — not whatever was on disk before. Never leaves uncommitted generated TS behind. |
| **B6** | If generated task code already exists, still restore to committed state. The harness still RUNS + RE‑GENERATES into the isolated temp dir to prove health, but writes nothing back and RESTORES to git HEAD. |
| **B7** | Spec‑driven deterministic assembly floor (OpenSpec spec wins). When a change pins an exact contract, the integrator ignores the LLM's generated command body and routes to `_assemble_contract_features`, injecting the authoritative contract verbatim. Guarantees build/test pass even when the LLM under‑delivers. |
| **B8** | Skill ↔ `AGENTS.md` bidirectional sync (never drift). The two files are the SAME source of truth. Any behaviour/constraint/command/pitfall change in one MUST be mirrored in the other before the change is done. |
| **B9** | Rootless nerdctl bind‑mount permissions (READ+WRITE). Whole repo world‑readable; container write targets world‑writable. Enforced by the `b9-perms` Makefile prerequisite. |
| **B10** | **NO hard‑coded generated TS/test code in Python** — only contract‑steered. Generated TS bodies live *only* in the change's `tasks.md`/`spec.md` markers; Python only parses + merges + injects verbatim. |
| **B11** | On generated‑TS failure: **fix the SPEC, then restore, then re‑run** — never edit TS by hand. Bounded ~5‑attempt self‑correct loop; only then may Python floor code be touched as last resort. |
| **B12** | Delivery gap — verified worktree TS MUST reach the target branch as the PR (`make openspec-flow NAME=<name> PUSH=1` → `git push feat/<name>`; corrections via `make openspec-redeliver` force-push to the SAME PR branch). NEVER a file copy into the parent working tree (worktree-confinement invariant). Never declare done while the worktree branch is undelivered. |
| **B13** | Python *floor* defects are fixed directly, not via spec round‑trips. If the defect is in the deterministic floor itself, fix `CodeIntegratorAgent` — that is the correct spec‑steered fix; only the *merge logic* is corrected, the contract TS body still comes from the spec. |
| **B14** | Commit/push gating for *new* code (human‑only, behaviour‑scoped). Code is committed ONLY if NEW; pushed ONLY if that new code is part of a behaviour. Floor/integrator Python fixes MAY be committed (and pushed only when part of a committed behaviour) **once**: `build-app`=0, `test-app`=0, passing‑test count **>** previous run, and all OpenSpec checks clean. Rule of thumb: commit only if new AND build works AND tests pass > last run AND OpenSpec clean; push only if that commit is the behaviour landing. **Never squash/rebase/force‑push.** |
| **B15** | **GitHub issue → local OpenSpec change via the OpenSpec CLI (seed‑then‑generate).** When a change is sourced from a GitHub issue, the agentic code MUST turn it into a local OpenSpec change by **shelling out to `openspec new change ticket<N>`** (the same CLI step a human runs) — never hand‑writing the directory, never a raw `Path.write_text` for the directory shape. `fetch_issue_agent.py` calls `openspec_loader.create_change_from_issue(url, title, body)` after the fetch; that scaffolds via the CLI, fills `proposal.md`/`specs/<cap>/spec.md`/`tasks.md` from the issue, and re‑points generation to `openspec:ticket<N>` so the rest of the loop runs offline. The change name is derived deterministically from the issue URL (`.../issues/20` → `ticket20`), so re‑runs are idempotent. The seeded `openspec/changes/ticket<N>/` is a RUNTIME artifact and MUST NOT be committed (extends B4); `ticket20`/`ticket22` e2e tests generate + clean it up in `finally`. Keeps B10 honest: the exact `openspec new change` a human runs is the one the pipeline runs. |
| **B16** | **Task‑completion discipline — tick as you verify, never leave open tasks, archive gate fails closed.** `make phase7-archive` runs `openspec_loader.assert_no_open_tasks` BEFORE `openspec archive` and refuses (non‑zero exit, no spec merge) if any `- [ ]` task remains. A change is "done" only when all tasks are ticked AND verified AND archived. `make loop-tasks` lists open/done per change so the backlog is never invisible. |
| **B17** | **Integration suite is a mandatory loop phase; no dead tests; live tests skip cleanly.** `make loop-harness` runs EIGHT loop stages plus a FINAL B8 doc-sync gate: a collection guard (gate 0), a strict TS test/command floor (gate 0.5), followed by six gates (1–6): `loop-collect` (hermetic collection guard) → `loop-ts-floor` (STRICT TS test/command floor — FAIL if the current branch's `describe`/leaf `it`/`test`/jest-collected/`addCommand` counts drop below `origin/main`) → `loop-unit` (mocked, hermetic) → `loop-unit-real` (REAL agent unit tests on live Ollama, no mocks) → `loop-e2e` (B1/B3 e2e) → `loop-integration` (broad suite) → `loop-build-app` → `loop-test-app` → `loop-secret-scan-tests` (secret-scanner pytest suite, containerized, real gitleaks, fail-closed; the actual gitleaks tree-scan lives in the pre-commit hook + CI, not the loop), then `check-docs-sync` (FINAL B8 gate — FAIL if any sync doc drifts on stage order / `loop-ts-floor` / B-range). No dead duplicates; live tests `skipif` cleanly on `OLLAMA_HOST`. |
| **B18** | **Run the agents' REAL unit tests, not only the mocked ones.** The loop MUST execute BOTH the hermetic mocked unit run (`loop-unit` → `test-agents-unit-mock`) AND the real, non‑mocked agent unit run (`loop-unit-real` → `test-agents-unit`, live Ollama) as gates 1 and 2. Reporting "agent tests green" after ONLY the mocked run is INCOMPLETE. `test-agents-unit` MUST be run when Ollama is reachable and its result reported alongside — not instead of — the mocked run. If Ollama is unreachable, `loop-unit-real` SKIPS (must not error) but the agent MUST state the real unit gate did not run. |
| **B20** | **NEVER declare a change "done" without running the loop gate first — hard pre-flight.** Before claiming any OpenSpec change complete (or "harness green/aligned/fixed"), run the gate and report real output. Preferred: `bash scripts/run-loop-harness.sh` (wrapper over `make loop-harness`, also `make loop-trigger`) — all eight stages. **HOW TO RUN: long-running `make` targets (`run-agentics`, `build-app`, `test-app`, `loop-harness`, `loop-e2e`, `deliver-change`, `phase7-archive`, `release-flow`) MUST be launched via `terminal(background=true)` — that call executes on the REAL HOST (`/home/asimov/repository/git/projects/obsidian-timestamp-utility`), where `make`/`docker`/rootless `nerdctl`/live Ollama all live. The foreground sandbox (`/workspace`) has NO docker/nerdctl and will say `docker: command not found` — that is EXPECTED and is NOT a blocker; the host has it.** The host provides rootless `nerdctl` AND a live Ollama (host-networked, so `127.0.0.1:11434` reaches it — B19), so `loop-unit-real` and `loop-e2e` are EXPECTED to RUN, not skip. Only STILL run the hermetic gates `make loop-collect` + `make loop-ts-floor` + `make loop-unit` (no external dep) when a stage truly cannot finish in the session; they MUST be green before any "done". Report honestly (PASS/SKIP/FAIL, failing stage named); never claim green if `loop-unit`/`loop-collect` is red; **never claim "can't run from here" — the host runs `make` for you.** Fix root cause and re-run. (B4/B14: no git commit/push from the gate.) |
| **B26** | **AGENT MAY COMMIT/MERGE ITS OWN CHANGES on a non‑main branch when the PRE‑COMMIT HOOK PASSES.** Permitted to `git commit` (and `git merge`/`git cherry‑pick`) its OWN work‑in‑progress on a feature branch so it can iterate productively. Bounded by: (1) branch guard — current branch MUST NOT be `main`/`origin/main`/protected; (2) hook guard — `git-hooks/pre-commit` (gitleaks + trailing‑whitespace) MUST pass; the agent commits only via the normal `git commit` path, NEVER `--no-verify`. Still forbidden (human‑only): `git push` (B14), `make squash-commits`, `git rebase -i` squash/fixup, `git reset --soft` collapse (B25). Adds commit/merge latitude on feature branches; does NOT lift no‑push/no‑squash/no‑force. (B21–B25 are documented in `AGENTS.md`.) |

---

## 7. How to use it (authoring a new feature)

### 7.1 Happy path (start → green → decide)

```bash
# 0. From the repo root, ensure a clean plugin baseline
git checkout HEAD -- src/main.ts src/__tests__/main.test.ts

# 1. Scaffold + describe the change
openspec new change insert-foo-command
#    ^ This is what CREATES openspec/changes/insert-foo-command/ (+ .openspec.yaml). It is the
#      ONLY directory scaffolder — never hand-create the folder. Then author the content:
#    edit openspec/changes/insert-foo-command/proposal.md
#    edit openspec/changes/insert-foo-command/specs/foo-modal/spec.md  (delta format)
#    edit openspec/changes/insert-foo-command/tasks.md
#       - checkbox plan (- [ ] X.Y ...)
#       - ## Contract  (```ts blocks with === CONTRACT_COMMAND/GENERATOR/MODAL === markers)
#       - ## Test Contract (```ts block with === TEST_CONTRACT_* === markers)
#
#    Alternative — drive the change FROM a GitHub issue: pass the issue URL instead of a local
#    change name. fetch_issue_agent fetches it once, then calls openspec_loader.create_change_from_issue()
#    which shells out to `openspec new change ticket<N>` to scaffold the directory and mirror the
#    issue into proposal/spec/tasks. Generation then runs locally against `openspec:ticket<N>`
#    (no further GitHub calls). The ticket20/ticket22 e2e tests exercise exactly this path.

# 2. Validate BEFORE implementing (must pass)
openspec validate insert-foo-command
openspec status --change insert-foo-command

# 3. Generate inside an isolated worktree
git worktree add ../worktrees/insert-foo-command -b feat/insert-foo-command
cd ../worktrees/insert-foo-command
export OLLAMA_HOST=http://localhost:11434
make run-agentics CHANGE=insert-foo-command      # backs up, runs pipeline, omission-guard

# 4. Verify (loop engineering)
make build-app                                   # tsc/rollup must exit 0
make test-app                                    # jest must pass
make test-app                                    # run again to confirm stability

# 5. Permanent regression proof (isolated, restores repo to git HEAD)
make test-agents-e2e

# 6. Re-verify the agentic suite after generation (real logic)
make verify-agentics-after-run

# 7. Deliver verified TS back onto the active branch (file copy, no commit)
cd <repo-root>
make deliver-change CHANGE=insert-foo-command

# 8. Archive the spec (spec only — NO git commit/push)
make phase7-archive CHANGE=insert-foo-command

# 9. YOU decide: review and commit/push the TS + tests deliberately (B4/B14)
```

### 7.2 When something breaks

Follow the §5.2 self‑correct loop:

1. Edit `tasks.md` `## Contract` / `## Test Contract` (markers, acceptance criteria).
2. Restore generated files: `git checkout HEAD -- src/main.ts src/__tests__/main.test.ts`
   (or use the `backups/<file>.<ts>.bak` snapshot).
3. Re‑run `make run-agentics` → `make build-app` + `make test-app`.
4. Each failed attempt = a *different* spec tweak. Never hand‑edit the generated TS.
5. After ~5 spec attempts still fail → fix the Python floor (`CodeIntegratorAgent`) last.

---

## 8. Command reference

| You want to… | Run |
|--------------|-----|
| Check the change is valid | `openspec validate <name>` |
| Show artifact completion | `openspec status --change <name>` |
| Generate the TS code+tests | `make run-agentics CHANGE=<name>` |
| Build the plugin (tsc/rollup) | `make build-app` |
| Run the plugin tests (jest) | `make test-app` |
| Prove the feature is really wired (regression) | `make test-agents-e2e` |
| Re‑check agentic logic after a run (real) | `make verify-agentics-after-run` |
| Pull verified worktree TS onto the branch | `make deliver-change CHANGE=<name>` |
| Fold the spec into the main list (spec only) | `make phase7-archive CHANGE=<name>` |
| Regenerate Python deps from `.in` | `make generate-requirements` |
| Apply the B9 perms floor manually | `make b9-perms` |
| Lint / format Python (via compose) | `make lint-python` / `make format` |
| Agent unit tests (mocked, fast) | `make test-agents-unit-mock` |
| Agent unit tests (real Ollama) | `make test-agents-unit` |
| Agent integration tests (real Ollama/GitHub) | `make test-agents-integration` |

> **Gotcha:** `make test-agents-e2e` and the real agent tests need **Ollama reachable**. Always
> set `OLLAMA_HOST=http://localhost:11434` first (or the e2e skips). Under rootless nerdctl the
> compose sets `OLLAMA_HOST=http://127.0.0.1:11434` directly (host-networked containers, so
> `host.docker.internal` does NOT resolve — use the coordinate `127.0.0.1` which reaches the live
> Ollama on the docker host). The host Ollama must be listening on that interface.

---

## 9. Known pitfalls (learned the hard way)

- **`nerdctl` + `docker compose run`** hardcodes `--interactive --tty`, so the container
  needs a real console (a bare file/pipe fails with *"provided file is not a console"*). The
  `docker compose run` commands in the Makefile are written PLAIN (no `script`, no `</dev/null`);
  the PTY is provided by the caller — `scripts/run-loop-harness.sh` wraps each `make <stage>` in
  `setsid script -qec "make <stage>; echo \$? > rcfile" /dev/null 2>&1 | tee -a log` so `script`
  can't be SIGSTOP'd by interactive job control (which otherwise hangs the loop at stage 0), and
  a human running `make` directly already has a real terminal console.
- **`docker compose build agentics`** needs `HOST_UID`/`HOST_GID` args with a fallback
  (`${HOST_UID:-1000}`). Passing an empty string overrides the Dockerfile default and breaks
  `groupadd`/`useradd`.
- **pip‑compile is SLOW** (5–15+ min, torch + transformers + langchain + langgraph + mcp). It
  only writes `requirements.txt` once the full solve completes — run `make generate-requirements`
  in the background; it is not stuck. **Never hand‑edit `requirements.txt`**; fix `requirements.in`.
- **`build-app`/`test-app` fail with `jest: not found` / `rollup: not found` in a worktree** →
  the worktree has no `node_modules`; the `app` compose mounts the repo `node_modules` **absolutely**
  (`…/node_modules:/app/node_modules`). A symlink does NOT work (target is outside the mount).
- **`TS1005: ',' expected` after generation** → the deterministic merge injected an
  `addCommand({...})` block without its trailing `);`. `_extract_balanced_blocks` must consume the
  `);` after the closing brace.
- **`PreTestRunner` reports `existing_tests_passed: 0` even on the original suite** → the
  jest‑output metric regex doesn't match this project's jest summary. That blocks self‑correction;
  trust `make test-app` manually as the authority rather than the in‑loop number.
- **Work in the real repo path** (`/home/asimov/repository/git/projects/obsidian-timestamp-utility`),
  NOT the `/workspace` decoy bind mount.
- **Two `main.ts` files exist.** `src/main.ts` is the real plugin. `agents/agentics/src/main.ts`
  (if present) is an e2e‑leak artifact and must never exist — the B3 harness asserts it doesn't.
- **Two `docs` guides historically.** The previous `docs/openspec-loop-harness-guide.md` and the
  root `new-loop-harness-open-spec-engineering-loop.md` are now redirects/stubs to this file.
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
  `hermes/skills/openspec-loop-harness.md` (B8). The reusable directive is the Hermes skill
  `request-to-openspec` (loaded at request entry).

---

## 10. Keeping the docs in sync (behaviour **B8**)

This file, `AGENTS.md`, and `hermes/skills/openspec-loop-harness.md` are the **same source of
truth**. When you change a behaviour, constraint, command, or pitfall in **any one** of them,
mirror it in the **other two** before considering the change done:

- Repo authority: `AGENTS.md` (phase flow + B1–B26 summary).
- Skill mirror: `hermes/skills/openspec-loop-harness.md` (operator‑level detail + pitfalls).
- This guide: `docs/openspec-engineering-loop-harness.md` (human‑readable technical reference).

Never leave two of these describing different behaviour. Example of a standing-rule change that
MUST stay in sync: the **request intake gate** (turn inbound Telegram / dashboard / terminal
requests into OpenSpec changes per the per-channel `openspec`-keyword trigger) appears in all
three files' General Rules / Known pitfalls, and the reusable directive is the Hermes skill
`request-to-openspec`.
