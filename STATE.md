# STATE.md — Loop State, Run Log & Metrics

## Run Log

| # | Date | Goal | Result | Iterations | Failure Mode | Fix |
|---|------|------|--------|------------|-------------|-----|
| — | 2026-06-25 | Initialize loop engineering | ✅ done | 1 | — | Created VISION.md, STATE.md, VERIFICATION.md; updated AGENTS.md |
| — | 2026-06-28 | Implement verify_and_retry + routing | ✅ done | 3 | Infinite retry loop | Moved retry counter from router to node function (LangGraph doesn't persist router state changes) |
| — | 2026-06-29 | Fix code generation to compile | ✅ done | 8 | LLM generates broken TS | Built text→pseudocode→code pipeline with deterministic 1:1 mapping |
| — | 2026-06-29 | Fix test generation to match code | ✅ done | 4 | LLM generates wrong function name | Deterministic test generation from export_name |
| — | 2026-06-29 | Single source of truth for naming | ✅ done | 3 | Two different names from different code paths | Removed LLM naming, derive everything from title |
| — | 2026-06-30 | Make test-app pass | ✅ done | 2 | Dagger timeout + stale files | Clean run, all 66 tests pass |
| — | 2026-06-30 | Programmatic 10-issue verification matrix | ✅ done | 1 | Unordered identifiers & filtered return statement | Extended workflow.py to support bare return identifiers and maintain OrderedDict structures. Fully compiled all 10 scenarios cleanly! |

## Cost Metrics

| Date | Task | Model | Est. Tokens | Result | Cost/Change |
|------|------|-------|-------------|--------|-------------|
| 2026-06-25 | Setup loop engineering | qwen3.5 | ~5K | ✅ accepted | Baseline |
| 2026-06-28 | Loop engineering + routing | qwen3.5 | ~15K | ✅ accepted | verify_and_retry, routing |
| 2026-06-29 | Text→pseudocode→code pipeline | qwen3.5 | ~30K | ✅ accepted | Core pipeline innovation |
| 2026-06-30 | Naming alignment + cleanup | qwen3.5 | ~10K | ✅ accepted | Single source of truth |
| 2026-06-30 | Programmatic 10-issue validation | qwen3.5 | ~25K | ✅ accepted | Extended edge-case coverage and fixed returns compiler bugs |

## Evaluation Metrics

| Date | Task | L1 Auto | L2 Test | L3 Spec | L4 Security | Judge | Iterations |
|------|------|---------|---------|---------|-------------|-------|------------|
| 2026-06-30 | Full pipeline (issue #20) | ✅ tsc pass | ✅ 66 Jest pass | ✅ integrated | ✅ no secrets | — | 3 |

## Security Audit

- Last re-audit: 2026-06-30
- Next re-audit: 2026-07-30
- Scope: token safety, plugin permissions, agent boundaries

## Failure Analysis

1. **Infinite retry loop** (2026-06-28): Router function modified state but LangGraph doesn't persist router state changes. Fixed by moving retry counter into node function.
2. **LLM code hallucination** (2026-06-29): qwen3.5:9b generates broken TypeScript (duplicate keywords, undefined vars). Fixed by deterministic code construction from pseudocode.
3. **Test/name mismatch** (2026-06-29): LLM naming step generated different names than code generation. Fixed by removing LLM naming entirely.
4. **Identifier filtering / Unordered Return in Pipeline** (2026-06-30): Under certain edge-case issue descriptions, variables returned without special punctuation got skipped, and set-based variable list resolved return variables in a random order. Fixed by exempting return expressions from standard word filters and switching tracking to lists.

## Notes
- 3 consecutive failures → STOP, escalate to human with full context
- Update this file after every loop run
- Key insight: LLM is reliable for text→pseudocode, unreliable for direct code generation
