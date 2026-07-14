# integrator-merge-refactor — Work Log

**Date:** 2026-07-14
**OpenSpec Change:** `integrator-merge-refactor`
**Branch:** `setup-loop-harness-openspec`

## Summary
Replaced the agentic integrator's fragile string-splice logic with a deterministic, line-aware
Plan-B merge (`_assemble_contract_features` in `code_integrator_agent.py`). The integrator now
strips any non-contract `addCommand` + any existing/LLM Modal of a given name from BOTH the
existing file and the LLM output, injects the authoritative contract command body (exact id/name,
calls the spec generator), and appends the spec Modal + spec generator only if absent. The merge is
idempotent (re-running never duplicates) and length-preserving (asserts merged >= input, guarding
against silent omission). This is the deterministic floor (B7/B10/B11): the LLM never holds the
pen; Python is the sole writer of `src/main.ts`.

## Verification Against Spec
- Requirement "Merge is idempotent + length-preserving": `_assemble_contract_features` asserts
  `len(merged) >= len(input)` and de-dupes. ✅ (validated via the greetings/uuid e2e runs — both
  green, contract command present, no prior logic dropped)
- Requirement "Contract derived from spec, not hardcoded": `_expected_contract_for_change` parses
  the change's spec/contract markers; no TS body literals in Python (B10 grep clean). ✅

## Key Decisions
- Capture Modal classes from the START OF THE SOURCE LINE (incl. leading `export `) through the
  matching close brace, then strip `export ` on re-inject — fixes a prior bug that dropped `export`
  and produced orphan classes breaking `tsc`.

## Current Status
Change complete; all technical tasks (1–8.3) verified via e2e green runs. Archiving.

## Recommended Next Steps
None — archive. (Subsequent changes `task-driven-ts-generation-e2e` + `agentic-self-correct-loop`
extend this floor; see those changes.)
