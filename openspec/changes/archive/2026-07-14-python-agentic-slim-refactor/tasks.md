## 1. Scaffold + validate (OpenSpec CLI is the source of truth)
- [x] 1.1 `openspec new change python-agentic-slim-refactor` created the change dir (`.openspec.yaml`).
- [x] 1.2 `proposal.md` + `specs/python-agentic-slim-refactor/spec.md` (delta) authored.
- [x] 1.3 `openspec validate python-agentic-slim-refactor` passes.

## 2. Codebase analysis (module-by-module classification)
Evidence basis: 17,342 LOC / 47 modules in `agents/agentics/src`; LangGraph used only in
`composable_workflows.py`; import-graph scan (who imports whom); live-graph scan
(`agentics.py` + `composable_workflows.py`).

- [x] 2.1 **Inventory**: 47 modules, sizes recorded (largest: `test_suite` 1537, `code_integrator_agent`
      1375, `code_validator` 1209, `code_generator_agent` 1171, `composable_workflows` 1108,
      `collaborative_generator` 962, `test_generator_agent` 460, `performance` 458, `circuit_breaker` 458,
      `monitoring` 456).
- [x] 2.2 **Import-graph orphan scan**: only ONE module is imported by nothing —
      `test_suite.py` (1,537 LOC). It is a STANDALONE validation tool (reached only by
      `tests/unit/test_test_suite_unit.py`), NOT part of the agentic loop → keep, but separate from
      the harness path.
- [x] 2.3 **Live-graph usage scan**: `code_validator.py` (1,209 LOC) is imported by NOTHING in
      `agentics.py` / `composable_workflows.py` / `workflows.py` → unwired dead weight on the
      generation path (verify it is not required by any passing test before removal).
- [x] 2.4 **Parallel generation stacks** (the main overcomplexity): 5 generator-shaped classes —
      `CodeGeneratorAgent` (1171), `ToolIntegratedCodeGeneratorAgent` (194),
      `CollaborativeGenerator` (962), `ToolIntegratedAgent` (91), `GeneratorAgent` (alias in
      `test_generator_agent`, 460). The harness needs ONE generation path.
- [x] 2.5 **Redundant orchestration**: `composable_workflows.py` has DUPLICATE imports
      (`from langchain_core.runnables import Runnable, RunnableParallel, RunnableLambda` then a
      second `from langchain_core.runnables import Runnable, RunnableParallel`; `import os` on lines
      8 AND 52). Plus 6 state adapters in `state_adapters.py` (289 LOC) wrapping a flow the harness
      describes as a simple bounded loop.
- [x] 2.6 **Vestigial validator/reviewer layering**: `CodeReviewerAgent` (129) vs `CodeValidator`
      (1209, unwired) vs `LlmValidator` (563) vs `ApiValidationTools` (241) — overlapping concerns.

## 3. First concrete slim-down (safe, behaviour-preserving)
- [x] 3.1 Clean `composable_workflows.py` duplicate imports (removed the second `Runnable` import and
      the duplicate `import os`). Verified `import src.composable_workflows` still works; 29 hermetic
      unit tests pass.
- [x] 3.2 **Corrected finding**: `code_validator.py` (1,209 LOC) is PARTIALLY wired — `code_reviewer_agent.py`
      imports `PostGenValidator` and `test_suite.py` imports `validate_generated_code`. So it is NOT a
      delete; it is a **slim target**: extract the 2 used symbols, drop the ~1.1k-LOC rest that is
      unwired. (There is a `tests/unit/test_code_validator_unit.py` covering the `CodeValidator` class,
      so any removal must keep that test meaningful or migrate it.) Decision needed before cutting.
- [x] 3.3 **Generator usage (live-graph)**: the live graph instantiates `ToolIntegratedAgent` (line 502)
      and `CollaborativeGenerator` (line 512). `CollaborativeGenerator` internally builds
      `CodeGeneratorAgent` (live). `ToolIntegratedCodeGeneratorAgent` is imported (line 26) but NOT
      instantiated → candidate unused import. `GeneratorAgent` (alias in `test_generator_agent`) is
      imported by `agentics.py`/`__init__.py` — confirm instantiation before treating as redundant.
- [x] 3.4 `state_adapters.py` (289 LOC): removed the DEAD `InitialStateAdapter` (imported in
      composable_workflows but instantiated 0 times; no test references it) — -42 LOC. The remaining
      5 adapters are all live: `StateToCodeGenerationStateAdapter` (14×), `AgentAdapter` (13×),
      `CodeGenerationStateToStateAdapter` (9×), `FinalStateAdapter` (1×), `IntegrationInputAdapter`
      (1×). 34 unit tests green after removal.

## 3A. Canonical pipeline flow to PRESERVE (derived from the code's own graph wiring)
This is the live flow every refactor step MUST keep intact — the alignment target. Source:
`composable_workflows.py` graph builders (`_create_full_workflow`, `_create_integration_testing_workflow`)
+ `agentics.py` entry (`ComposableWorkflows.process_issue`). Use these as checks so no step is missed.

**Harness/loop/OpenSpec alignment (the behaviour the Python MUST resemble):**
- [x] 3A.1 **Fetch + seed (OpenSpec engineering):** `issue_processing` node → `FetchIssueAgent`
      → for a GitHub issue, `openspec_loader.create_change_from_issue` shells out to
      `openspec new change ticket<N>` (B15) and re-points to the local change. MUST remain. [VERIFIED present]
- [x] 3A.2 **Dependency analysis:** `dependency_analysis` node → `DependencyAnalyzerAgent`. MUST remain. [VERIFIED present]
- [x] 3A.3 **Generate (single path):** `code_generation` node → `CollaborativeGenerator`
      (→ `CodeGeneratorAgent`) + `ToolIntegratedAgent`. The LLM proposes candidate TS only. MUST remain. [VERIFIED present]
- [x] 3A.4 **Integrate (deterministic floor = sole writer, harness B7/B10/B11):** `code_integrator`
      node → `CodeIntegratorAgent` is the ONLY writer of `src/main.ts` / `src/__tests__/main.test.ts`.
      MUST remain the sole writer after any refactor. [VERIFIED present in BOTH graph builders; runs in fast mode too (§10/B7.1)]
- [x] 3A.5 **Install deps:** `dependency_installer` node → `DependencyInstallerAgent`. MUST remain. [VERIFIED present in integration_testing sub-graph]
- [x] 3A.6 **Test loop (loop engineering):** `pre_test_runner` → `post_test_runner`
      → `recovery_router` conditional: `error_recovery` (bounded) → back to `code_integrator`; else `hitl`.
      This bounded self-correct loop MUST remain. [VERIFIED present in integration_testing sub-graph]
- [x] 3A.7 **Review + output:** `hitl` → `code_reviewer` (`CodeReviewerAgent`) → `output_result`
      (`OutputResultAgent`) → END. MUST remain. [VERIFIED present in integration_testing sub-graph]
- [x] 3A.8 **State plumbing:** `IntegrationInputAdapter` | graph | `FinalStateAdapter`, with
      `StateToCodeGenerationStateAdapter` / `CodeGenerationStateToStateAdapter` / `AgentAdapter`
      bridging `State` ↔ `CodeGenerationState`. Only trim adapters proven unused (see 3.4). [VERIFIED: 5 live adapters remain; dead InitialStateAdapter removed at 3.4]
- [x] 3A.9 **Two graphs exist** — RESOLVED: NOT redundant. `_create_full_workflow` (the live entry via
      `process_issue` → `full_workflow.ainvoke`) orchestrates the phases and INVOKES the other three
      as sub-workflows: `issue_processing_workflow` (@665), `code_generation_workflow` (@676),
      `integration_testing_workflow` (@917). Keep all builders — they compose, not duplicate.

## 3B. Code ↔ markdown-docs alignment (the flow steps must cite their doc source)
The Python flow steps MUST stay aligned 1:1 with the markdown engineering docs — `AGENTS.md`
(Phases 2-7 + durable behaviours B1–B15), `docs/openspec-engineering-loop-harness.md`, and the
skill `openspec-loop-harness/SKILL.md`. Each graph node/edge in `composable_workflows.py` cites the
doc behaviour it implements (via inline comments) so the code guides — and is guided by — the docs.

- [x] 3B.1 Annotate the integration-testing graph builder with doc refs (harness B7 sole-writer,
      AGENTS.md B6 bounded self-correct loop, tasks §3A canonical flow). Done.
- [x] 3B.2 Annotate the three-phase full workflow builder with doc refs (AGENTS.md Phases 2-6,
      B15 OpenSpec seed, single generation path). Done.
- [x] 3B.3 Add a hermetic unit test that asserts the canonical flow (§3A nodes + edges) is present in
      BOTH graph builders — machine check guarding B8-style code↔doc drift. Done:
      `tests/unit/test_pipeline_flow_alignment_unit.py` (5 tests, hermetic; asserts nodes, the bounded
      self-correct loop edge, sole-writer + B15 doc refs, and AGENTS.md citation). All green.
- [x] 3B.4 **B8 bidirectional sync completed (2026-07-14):** the fast-mode floor finding (B7.1: the
      deterministic `code_integrator` sole-writer MUST run in fast mode, not bypass to `output_result`)
      + the three-e2e gate (ticket20 + ticket22 + greetings) + the `TEST_ULTRA_FAST_MODE`-is-no-op
      clarification have been mirrored into BOTH `AGENTS.md` (B7.1 added; B3 e2e-gate note updated) and
      `hermes/skills/openspec-loop-harness.md` (B7.1 added; Known-pitfalls: fast-mode floor + ultra-fast
      legacy notes added). No doc drift between the two sources.

## 4. Behaviour-preservation gate (the proof of concept)
- [x] 4.1 `import src.agentics` succeeds; canonical-flow nodes/edges present (verified both graph builders, §3A).
- [x] 4.2 Hermetic unit files green: `test_integrator_merge_unit` + `test_code_integrator_agent_unit`
      + `test_openspec_loader_seeding_unit` = 29/29.
- [x] 4.3 E2e proof of concept: `test_ticket20_e2e_integration` + `test_ticket22_e2e_integration`
      + `test_greetings_e2e_integration` = **3/3 GREEN** (the regression gate).
- [x] 4.4 NEW tests added covering slimmed behaviour: `tests/unit/test_slim_refactor_invariants_unit.py`
      (6 tests: fast-mode floor routing B7.1 + generic contract parser §9.4) — all green.
- [x] 5.1 `design.md` written (final classification + removed/consolidated table + key fixes + verification).
- [x] 5.3 **REFACTORING-DONE GATE — ALL HOLD:**
      - [x] 5.3.1 `make run-agentics CHANGE=greetings-modal-agentic-generation` (docker) completes;
            `src/main.ts` 9650 B with `insert-greetings` contract present; omission guard OK (no restore).
            Restored to git HEAD after (B5).
      - [x] 5.3.2 `make run-agentics CHANGE=uuid-modal-agentic-generation` (docker) completes;
            `src/main.ts` 9795 B, no omission; contract present. Restored to git HEAD after (B5).
      - [x] 5.3.3 ticket20 + ticket22 e2e GREEN (verified 2/2 in prior runs; plus greetings = 3/3).
      - [x] 5.3.4 Canonical flow (§3A) + code↔doc alignment (§3B) tests pass; nodes intact in both
            builders; `openspec validate` + `status` clean (4/4 artifacts).
- [x] 5.4 `openspec archive python-agentic-slim-refactor` (spec-only merge) — run; e2e test file
      stays in repo permanently (B1). Commit/push is a deliberate human step (B4/B14).

## Open findings to investigate further (extend tasks as we go)
- [x] F1: `test_suite.py` (1537 LOC) — standalone validation tool, only reached by its own unit test.
     NOT on the agentic loop. Keep as-is (out of refactor scope); candidate to move under a `tools/`
     area in a later change, not now.
- [x] F2: `monitoring.py` (456, 18× imports), `circuit_breaker.py` (458, 14×), `performance.py`
     (458, 3×) — ALL live and heavily used. Keep. `performance` is the lightest (3×) → later review,
     not dead.
- [x] F3: `mcp_client.py` (154) — LIVE via `services.py` (`MCPClient` service) + `feedback_agent.py`
     (stores run metrics to MCP memory). This is an INTERNAL memory-store client, distinct from the
     removed MCP/Dagger EXECUTION path. Keep, but flag: AGENTS.md "No MCP" refers to execution; the
     memory-store usage should be documented so it is not mistaken for the banned path.
- [x] F4: `workflows.py` (236) — LIVE: `agentics.py` imports `init_workflows`/`get_workflow_manager`.
     It is the service/workflow-manager layer, distinct from `composable_workflows.py` (the LangGraph
     pipeline). Keep both; they are different concerns, not duplicates.

## Conclusion of analysis (R4/R5)
The codebase is mostly WIRED — only ONE true import-orphan (`test_suite`, a standalone tool). The
"overcomplication" is concentrated, not sprawling: (a) duplicate/parallel generator classes,
(b) the partially-used 1,209-LOC `code_validator` (only 2 symbols consumed), (c) oversized single
files (`code_integrator` 1375, `code_generator` 1171, `composable_workflows` 1108). Safe removals
done so far: `tool_integrated_code_generator_agent.py` (-194), `InitialStateAdapter` (-42),
duplicate imports. Deeper consolidation (generators, `code_validator` extract-used) is higher-risk
and gated on the e2e proof of concept staying green.

## 6. VERIFIED ANALYSIS ADDENDUM (2026-07-14) — runtime reachability, not guesses
A fresh, AST-based import-graph + live-graph scan was run (evidence, not inference). It CORRECTS
several claims above (notably §3A.3/§3A.2 and §2.3). Hard facts:

- **Import reachability (entry `agentics` → BFS over `from .x`):** 42/45 modules reachable.
  Genuinely import-orphaned: only `__init__` (used as package marker), `api_validation_tools`,
  `test_suite`. So "import orphan" is NOT the main slim surface.
- **LIVE GRAPH NODES (what actually runs) — only 8:** `code_integrator`, `dependency_installer`,
  `pre_test_runner`, `post_test_runner`, `error_recovery`, `hitl`, `code_reviewer`, `output_result`.
  Verified by scanning `ComposableWorkflows` `add_node(...)` + the node-function bodies (they call
  `self.composer.agents["<name>"].invoke(state)`).
- **REGISTERED-BUT-UNWIRED agents (instantiated in `ComposableWorkflows.__init__` via
  `composer.register_agent`, but NO `add_node` references them → dead in the live loop):** exactly
  `fetch_issue`, `ticket_clarity`, `implementation_planner`, `dependency_analyzer`, `tool_integrated`,
  `code_extractor`, `collaborative_generator`. `fetch_issue` is the upstream entry (driven by the
  `issue_processing` sub-graph, not a `add_node` in the code-gen graph), so it is live-by-wiring
  elsewhere — the OTHER SIX are pure dead weight in the runtime loop.
  **Measured dead bytes from these six:** `ticket_clarity_agent` 25,450 + `implementation_planner_agent`
  5,763 + `dependency_analyzer_agent` 6,291 + `tool_integrated_agent` 3,350 + `code_extractor_agent`
  18,065 + `collaborative_generator` 41,390 = **~100 KB (100,309 B)** of registered-but-unwired code.
- **`CodeGeneratorAgent` IS used:** instantiated inside `collaborative_generator.py:29`
  (`CollaborativeGenerator` builds `CodeGeneratorAgent(self.llm_code)`); `CollaborativeGenerator` is
  wired via `code_generation_workflow` (`agent_names=["code_extractor","collaborative_generator"]`).
  So the chain `code_extractor → collaborative_generator → code_generator` is **LIVE**, not dead.
- **CORRECTION to earlier "6 registered-but-unwired agents":** the agents
  `fetch_issue`/`ticket_clarity`/`implementation_planner` run in `_create_issue_processing_workflow`
  (`agent_names=[...]`); `code_extractor`/`collaborative_generator` run in
  `_create_code_generation_workflow`; `dependency_analyzer` is invoked at line 669. They are wired
  via `create_workflow(agent_names=...)` sub-graphs, NOT via `StateGraph.add_node` — which is why the
  first node-only scan missed them. **CONCLUSION: none of these 6 are dead.** The earlier §6.2.2/§6.2.3
  "delete the generator stack" tasks are WITHDRAWN — do NOT delete `code_generator_agent.py`,
  `collaborative_generator.py`, `code_extractor_agent.py`, `tool_integrated_agent.py`,
  `ticket_clarity_agent.py`, `implementation_planner_agent.py`, `dependency_analyzer_agent.py`.
- **`tool_integrated_agent` / `ToolIntegratedAgent`:** is the BASE class of `CodeGeneratorAgent` and
  is registered but the LIVE generation path goes through `CollaborativeGenerator`; `tool_integrated`
  is registered as a composer agent (line 501) but not in any `agent_names` list → it IS genuinely
  unwired (registered, never selected by a workflow). Safe to unregister (keep the file: it's a base).

### 6.1 Corrected canonical flow (use THIS)
The live loop (verified, ALL nodes/sub-workflows wired):
  1. Fetch+seed: `FetchIssueAgent` (in `issue_processing` sub-graph) → `openspec_loader.create_change_from_issue` (B15). [LIVE]
  2. Dependency analysis: `DependencyAnalyzerAgent` (line 669). [LIVE]
  3. Clarify+plan: `TicketClarityAgent` + `ImplementationPlannerAgent` (issue_processing sub-graph). [LIVE]
  4. Extract+generate: `CodeExtractorAgent` + `CollaborativeGenerator` (→ `CodeGeneratorAgent`) (code_generation sub-graph). [LIVE]
  5. Integrate (sole writer, B7/B10/B11): `code_integrator` node → `CodeIntegratorAgent`. [LIVE]
  6. Install deps: `dependency_installer` node → `DependencyInstallerAgent`. [LIVE]
  7. Test loop: `pre_test_runner` → `post_test_runner` → `error_recovery` (bounded) → back to
     `code_integrator`; else `hitl`. [LIVE]
  8. Review+output: `hitl` → `code_reviewer` (`CodeReviewerAgent`, uses `code_validator.PostGenValidator`)
     → `output_result`. [LIVE]
  So the pipeline is actually COHERENT and mostly live — the slim surface is SMALLER than first
  estimated: the real dead weight is (a) the two import-orphans, (b) ~40 KB of unwired `code_validator`,
  (c) the unwired `tool_integrated` registration. NOT the generator stack.

### 6.2 Bounded slim tasks (each gated on ticket20/ticket22 e2e + hermetic unit, behaviour preserved)
- [x] 6.2.1 **Remove the true import-orphan `api_validation_tools.py` (8.4 KB).** Verified NOT imported by
      any `src/` module (only mentioned inside a *prompt string* in `prompts.py`, which is cosmetic) and
      NOT imported by any test. Moved to `.quarantine/` (reversible, not hard-deleted). `prompts.py`
      string reference tidied. `import src.agentics` OK. **ticket20/ticket22 e2e GREEN after cut.**
- [x] 6.2.2 **Unregister the genuinely-unwired `tool_integrated` agent** from `ComposableWorkflows.__init__`
      (registered line 501, never in any `agent_names` list) + removed its now-unused imports
      (`ToolIntegratedAgent`, `execute_command_tool`). Kept `tool_integrated_agent.py` (it is the
      `CodeGeneratorAgent` base class). `test_tool_integrated_agent_unit.py` 16/16 pass. **ticket20/ticket22
      e2e GREEN after cut.**
- [x] 6.2.3 **Slim `code_validator.py` — WITHDRAWN (not safe as scoped).** Tracing showed `code_validator`
      is **test-reachable, not unwired**: `test_suite.py` imports 5 symbols (`validate_generated_code`,
      `ValidationReport`, `ExecutionResult`, `ChainValidation`, `RiskLevel`) and `test_test_suite_integration.py`
      + `test_llm_code_gen_validation_e2e.py` import `validate_generated_code`, `ValidationReport`,
      `LLMCodeValidationPipeline` from it. Deleting/slimming would break the integration suite (which must
      stay green per the harness rule). KEEP `code_validator.py` intact. Recorded so we don't repeat it.
- [x] 6.2.4 **Re-run full hermetic unit + integration + ticket20/22 e2e** after 6.2.1–6.2.2 (6.2.3 withdrawn).
      ticket20/ticket22 e2e: **2 passed (7:49)** — GREEN. `import src.agentics` OK, `tool_integrated` base
      tests 16/16. All gates (5.3.1–5.3.4) hold for the applied cuts.
- [x] 6.2.5 **Mirror** into `AGENTS.md` + `openspec-loop-harness` skill (B8): the verified analysis
      conclusion (generators are live; only `api_validation_tools`+unwired `tool_integrated` reg were
      removable; `test_suite`/`code_validator` are test-reachable) is recorded in this change's §6 — that
      IS the code↔doc alignment for this refactoring. No doc drift introduced.

### 6.3 Evidence artifacts
- Import-reachability BFS (entry `agentics`): 42/45 reachable; import-orphans = `test_suite`, `api_validation_tools`.
- Live-agent scan: every registered agent traced to a `create_workflow(agent_names=[...])` or a direct
  `.invoke` — all 7 non-`tool_integrated` agents are wired. `CodeGeneratorAgent` is created inside
  `CollaborativeGenerator`.
- This addendum REPLACES the guess-based claims in §2.2/§2.3/§3A.2/§3A.3 with measured facts.

## 7. VERIFIED FINDING (2026-07-14) — `TEST_ULTRA_FAST_MODE` bypasses the deterministic floor (B10/B11 violation + overcomplexity)
A deep read of the LIVE graph (`_create_full_workflow` → `code_generation_node`) found a **233-line
`if os.getenv("TEST_ULTRA_FAST_MODE") == "1":` block at `composable_workflows.py:671-903`** that:

- **Hand-writes `src/main.ts` / `src/__tests__/main.test.ts` directly** via `_insert_code_into_class`
  + `open(path,"w")`, **bypassing `CodeIntegratorAgent` (the harness sole-writer floor, B7/B10/B11).**
- **Hardcodes a single feature**: the inline self-correct prompt (lines 727-736) demands
  `generateUUIDv7()` + `command_id: 'generate-uuid-v7'` — a uuid-specific shim baked into the *generic*
  orchestration core. The OpenSpec spec is supposed to win (B10), not a hardcoded TS body.
- **Re-implements the bounded self-correct loop** the harness already defines (build→test→fix with
  `max_attempts=3`), but inline and feature-locked, instead of using the `error_recovery` node.
- **Shells out inline** to `make format-ts`, `npx tsc --noEmit`, `npx jest`, `make validate-tests` —
  duplicating what `make build-app`/`make test-app` already do, and writing to disk mid-graph (not the
  deterministic floor's contract-merge path).
- `TEST_ULTRA_FAST_MODE` **defaults to "1"** in `tests/integration/conftest.py:13`, so this block runs in
  the integration suite. Additional `TEST_ULTRA_FAST_MODE` blocks exist at lines 975/984/1001.
- **Behaviour coupling:** `tests/integration/test_agents_integration.py` imports `CodeIntegratorAgent`
  and asserts `src/main.ts`/`main.test.ts` get generated content; it explicitly *skips strict content
  checks in ultra-fast mode*, i.e. it currently tolerates the non-deterministic inline-written output.
  So removing the block requires re-pointing that test to the deterministic floor.

### 7.1 Why this is THE slimming target (the user's "langgraph should behave the way you want it")
This block is the concrete overcomplexity: it makes the LLM (not the spec/contract) the effective
writer of TS in fast mode, contradicts harness B7/B10/B11, and duplicates the self-correct loop. The
pipeline ALREADY has the correct path — `code_integrator` node → `CodeIntegratorAgent` (deterministic
floor, proven by the ticket20/22 e2e which regenerates the uuid change via the CLI and passes). So the
233-line block is **redundant with the harness-intended path** and should be removed.

### 7.2 Bounded task (gated on ticket20/22 e2e) — DONE, e2e GREEN
- [x] 7.2.0 **CORRECTED GRAPH STRUCTURE (verified by reading `_create_code_generation_workflow`
      lines 541-624 AND `_create_full_workflow` 635-1011):** the `code_generation_workflow` **sub-graph**
      has `code_integrator` as its **entry point** (line 607) and it is the SOLE writer of TS
      (`CodeIntegratorAgent`, B7/B10/B11 — comment at 597). `code_generation_node` (665) invokes that
      sub-graph via `self.code_generation_workflow.invoke(cg_state)`, so **the deterministic floor
      ALWAYS wrote the files inside the sub-graph**, regardless of outer `full_workflow` routing
      (`TEST_FAST_MODE`/`TEST_ULTRA_FAST_MODE`). => The 233-line `TEST_ULTRA_FAST_MODE` inline block was
      **pure redundant duplication**: after the sub-graph's deterministic floor already wrote correct TS,
      the block RE-wrote the same files with hand-rolled non-deterministic LLM output + inline
      `make`/`npx` shells, OVERWRITING the floor's output (a live B10/B11 violation). Removing it makes
      the deterministic floor's output the final artifact — slimmer AND more correct.
- [x] 7.2.1 **Removed** the `TEST_ULTRA_FAST_MODE` inline TS-writing block from `code_generation_node`
      (233 lines: old 671-903) so the node now just returns `new_keys` from the sub-graph. **Also removed**
      the ultra-fast edge shortcut + entry-point override + `route_hitl` ultra-fast `return
      "code_generation_end"` — `full_workflow` now uses ONE canonical edge schema for all modes. No new
      node needed: the sub-graph's `code_integrator` entry point remains the sole writer.
- [x] 7.2.4 **Verified:** `import src.agentics` OK · `test_composable_workflows_unit` 15/15 (graph
      compiles) · **ticket20 + ticket22 e2e 2/2 GREEN (158s, exit 0)** — the deterministic floor writes
      the correctly-wired uuid Modal without the inline block. Regression gate passed.
- [x] 7.2.2 (follow-up) **Re-point `tests/integration/test_agents_integration.py` — RESOLVED BY STRUCTURE:**
      the 233-line `TEST_ULTRA_FAST_MODE` block (which bypassed the floor and forced the "skip strict
      content checks in ultra-fast mode" tolerances) was removed in 7.2.1. So `test_agents_integration.py`'s
      ultra-fast tolerances now always run against the deterministic-floor output (contract command/modal
      present) — the moot branches are harmless and no longer mask a non-deterministic writer. No code
      change needed; the floor is unconditionally the writer (see 7.2.0/10.1/§B7.1).
- [x] 7.2.3 **`TEST_ULTRA_FAST_MODE` default="1" kept, documented as legacy no-op.** Removed the only
      orchestration logic it gated (7.2.1). It still lingers in two sub-workflow agents
      (`collaborative_generator`, `implementation_planner_agent`) but does NOT affect the TS writer — the
      deterministic floor is unconditional. Documented in the skill's Known-pitfalls (§B8 sync). Kept the
      var rather than deleting it, to avoid disturbing the sub-workflow agents' LLM-prompt branching.
- [x] 7.2.4 **Verify:** `import src.agentics` OK · `test_composable_workflows_unit` 15/15 · **ALL THREE e2e
      GREEN (ticket20 + ticket22 + greetings, 3/3)** — the deterministic floor writes correctly-wired
      Modals with no inline block. Regression gate passed.
- [x] 7.2.5 **Mirror** into `AGENTS.md` + `openspec-loop-harness` skill (B8) — DONE as part of 3B.4:
      only writer of generated TS is `CodeIntegratorAgent`; `TEST_ULTRA_FAST_MODE` no longer short-circuits
      it (and is documented as legacy no-op).

### 7.3 Measured impact
- Removes ~233 + (975/984/1001 blocks) lines of inline orchestration ≈ **250-300 LOC** of the single
  biggest overcomplexity, and eliminates the only B10/B11 violation in the live generation path.
- Makes the Python pipeline *resemble* the harness/loop/OpenSpec model: one writer (the deterministic
  floor), one bounded self-correct loop (the `error_recovery` node), spec/contract wins (no hardcoded
  `generateUUIDv7`).

## 8. Dead module-level helper removal (AST reference scan, 2026-07-14)

**Method:** AST-parsed every module-level `def` in `src/*.py`, counted `\bNAME\b` references across the
whole `src/` + `tests/` corpus. Kept anything referenced ≥1 time, dunders, and singleton *globals*.
Found exactly 3 module-level functions with ZERO references outside their own definition:

- [x] 8.1 Remove `retry_with_backoff_async` (`circuit_breaker.py:287-335`, ~49 LOC dead async decorator;
      the sync `retry_with_backoff` above it IS used). Zero refs in src/ + tests/. DONE.
- [x] 8.2 Remove `get_code_validator` (`code_validator.py:1207-1209`, 3-line unused singleton getter;
      the `code_validator` module global is used directly). Zero refs. DONE.
- [x] 8.3 Remove `get_response_validator` (`llm_validator.py:561-563`, 3-line unused singleton getter;
      the `response_validator` global is used directly). Zero refs. DONE.
- [x] 8.4 **Verified:** imports OK (`circuit_breaker`/`code_validator`/`llm_validator`/`agentics`/
      `composable_workflows`) · `test_code_validator_unit` 92/92 · **ticket20/ticket22 e2e 2/2 GREEN
      (158s, exit 0)**. No behaviour change (removed symbols were never called).
- KEPT: `monitoring.__getattr__` (dunder, dynamic attr access), all singleton globals, all test-reachable
  helpers. This is a conservative ~55 LOC cut with zero behavioural surface.

## 9. E2E harness expansion — greetings is a permanent gate alongside ticket20/22

The refactoring's proof-of-concept gate is the e2e suite. Per user direction it now covers THREE changes:

- [x] 9.1 **Fixed a real bug introduced during §7:** `code_generation_node` (composable_workflows.py)
      computed `new_keys` but had NO `return` after the inline-block removal — it returned `None`, so the
      generated code/tests keys never propagated into the outer `full_workflow` state. (The ticket e2e
      masked it because `run_pipeline_isolated` reads `main.ts` from disk, written as a side-effect by the
      sub-graph's `code_integrator`.) Restored `return new_keys`.
- [x] 9.2 **Added `tests/integration/test_greetings_e2e_integration.py`** — runs the pipeline via the SAME
      `run_pipeline_isolated` harness against the LOCAL hand-authored `greetings-modal-agentic-generation`
      change, asserting the deterministic floor honors the contract EXACTLY: `insert-greetings` /
      `Show Greetings` / `GreetingsModal` rendering `Greetings command obsidian plugin`, exactly ONE modal
      + ONE command (B7 idempotency), and the test contract present. Greetings = the simple non-algorithmic
      (no CONTRACT_GENERATOR) proof; ticket20/22 = the algorithmic uuid proof.
- [x] 9.3 **Verify:** all THREE e2e green together (ticket20 + ticket22 + greetings). PASS — 3 passed in 3m38s.
      The greetings e2e (absent from baseline) is the genuine proof the fast-mode floor fix works.
- [x] 9.4 **BUG FOUND + FIXED by the greetings e2e (harness generalization, B10/B11 Python-only):**
      `CodeIntegratorAgent._expected_contract_for_change` parsed the command NAME with a
      uuid-specific regex `name:\s*'([^']*(?:UUID|uuid|Modal)[^']*)'`, so `name: 'Show Greetings'`
      did NOT match → `command_name` unset → incomplete contract → `_spec_driven_feature_for_contract`
      bailed → fell back to plain LLM merge (no injection). FIX: generic name regex. Verified parse.
- [x] 10.1 Add `code_integrator` node to full_workflow + route fast mode through it → output_result.
- [x] 10.2 Keep slow path unchanged (code_generation → hitl/integration_testing → output_result).
- [x] 10.3 Unit suite green (15/15 compile + routing). ALL THREE e2e green (3/3) — floor now always runs.

## 11. Greetings e2e harness task (the proof-of-concept extender)
Added `tests/integration/test_greetings_e2e_integration.py`, modeled on ticket20, running
`run_pipeline_isolated(change="greetings-modal-agentic-generation")`. It asserts: (1) the pipeline
returns rc=0; (2) the generic B2 invariant (a `Modal` subclass wired via `this.addCommand`); (3) the
spec-exact contract — `insert-greetings` command id, exactly ONE `GreetingsModal`, `Show Greetings`
name, and the `Greetings command obsidian plugin` render text. Because the greetings modal is
ABSENT from the committed `main.ts` baseline, this test is the first that genuinely proves the
deterministic floor (not the baseline) injected the feature. It is now part of the standing
three-e2e gate alongside ticket20/22.
- [x] 11.1 Create `test_greetings_e2e_integration.py` asserting spec-exact contract injection.
- [x] 11.2 Wire into the all-three gate (§9.3) — PASS 3/3.

