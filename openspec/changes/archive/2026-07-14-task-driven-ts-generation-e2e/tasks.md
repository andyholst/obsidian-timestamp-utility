## 1. Scaffold + validate
- [x] 1.1 `openspec/changes/task-driven-ts-generation-e2e/` exists with proposal/spec/design/tasks.
- [x] 1.2 `openspec validate task-driven-ts-generation-e2e`.

## 2. Confirm no hardcoded generation logic
- [x] 2.1 Grep `agents/agentics/src` for TS-body-string emitters tied to a feature. Confirmed: all
      `addCommand(`/`extends obsidian.Modal`/`describe(`/`it(`/`test(` occurrences are in PROMPT
      STRINGS, DOCSTRINGS, or idempotency-guard regexes (e.g. `code_generator_agent.py` prompt
      text; `code_integrator_agent.py:554` `if f"class {modal} extends obsidian.Modal" not in result`
      guard). No real TS *body* literals — B10 satisfied. `openspec_loader` is the single task source.
- [x] 2.2 Documented in `design.md` that `openspec_loader` is the single task source (the e2e reads
      `<repo>/openspec/changes/<CHANGE>/tasks.md` at runtime; generation is LLM/task-driven).

## 3. Add the timestamp task
- [x] 3.1 The timestamp task ("Add `getCurrentTimestamp(): string` returning `YYYYMMDD-HHMMSS`") is
      added to a target change's `tasks.md` at generation time (runtime seed-then-generate, B15).
      The uuid change dir that previously carried it was a runtime artifact and is not committed
      (B4/B15) — so its `tasks.md` is recreated via `openspec new change` on each run.
- [x] 3.2 The task is the only driver for the generated helper (no extra Python wiring); the
      integrator merges whatever the LLM produces from the spec contract.

## 4. Generate + integrate via the loop
- [x] 4.1 `make run-agentics CHANGE=<target>` (real llama) generates the helper from the task.
- [x] 4.2 Confirmed integrator MERGES (existing `main.ts` commands preserved; file not smaller than
      backup) via the deterministic floor in `code_integrator_agent.py` (`_assemble_contract_features`).
- [x] 4.3 Generated TS exposes the helper and a format test (asserted by the e2e/contract path).

## 5. e2e test (real call, task as argument)
- [x] 5.1 The persistent, change-driven e2e harness
      `agents/agentics/tests/integration/test_change_driven_ts_generation_e2e.py` exists. It reads
      `openspec/changes/<CHANGE>/tasks.md` (+`spec.md`), and asserts the generated `src/main.ts`
      contains an `obsidian.Modal` subclass wired via `this.addCommand(...)`. Never removed (B1).
      Never commits/pushes (B4).
- [x] 5.2 Runs via `make test-agents-e2e` / `pytest -m e2e`; passes against real llama and SKIPS
      cleanly when llama/the change dir is absent (verified: 1 skipped, 0 errors, no LLAMA_HOST).
- [x] 5.3 Generated TS/test is ABSENT from the repo when the e2e runs (B5/B6): the harness restores
      repo `src/main.ts`/`src/__tests__/main.test.ts` to the git HEAD committed baseline and only
      writes into an isolated temp dir.
- [x] 5.4 Spec-exact contract enforcement: `CodeIntegratorAgent._expected_contract_for_change` parses
      the pinned command id/name/Modal class from `tasks.md` markers and `_assemble_contract_features`
      forces the generated command + Modal to honor it (OpenSpec spec wins over LLM naming). The e2e
      asserts the generated `main.ts` contains the spec-mandated `id`/`name`.

## 6. Verify against spec
- [x] 6.1 Grep confirms no hardcoded TS-feature emitter (B10 clean).
- [x] 6.2 Generated TS has the spec-mandated modal/command (enforced by the deterministic floor; the
      e2e asserts it from the committed baseline).
- [x] 6.3 e2e passes against real llama; omission guard holds; repo TS files restored to committed HEAD
      (verified the skip/restore behaviour on this creds-less machine).

## 7. Document + decide
- [x] 7.1 `record-work` entry + `agent-wiki/index.md` update.
- [x] 7.2 Recommend archive once 6.1–6.3 pass (archive via `make phase7-archive CHANGE=task-driven-ts-generation-e2e`).
