## Why

The current `code_integrator_agent` merges generated TypeScript into `main.ts` using
**whole-file brace-surgery** (`_extract_balanced_blocks` + `integrate_code_deterministic` with
global brace counting). That path is brittle and has repeatedly produced corrupt output
(e.g. orphaned `export ` tokens, a generator method appended *outside* the plugin class, and a
malformed LLM blob with literal `\n` escapes that defeated brace balancing). The loop cannot
self-correct against these because there is no pinned, simple, verifiable merge contract.

We need a **Plan B**: a deterministic, *anchor-based* merge that operates on stable markers
(imports block, `onload()` method, `export default class TimestampPlugin` closing brace, and
file end) instead of scanning the entire file for braces. The OpenSpec spec contract (command
id / name / Modal class) is the single source of truth, so the deterministic output is
authoritative and the LLM output is only merged when it does not conflict.

## What Changes

- Replace whole-file brace surgery with an **anchor-based merge**:
  - imports: append any missing `import` lines after the existing import block.
  - commands: inject spec-contract `this.addCommand({...})` blocks into `onload()` (before its
    closing `}`), preserving every existing command.
  - Modal: append the generated `obsidian.Modal` subclass as a **top-level** class at file end
    (idempotent: only if absent).
  - generator: append the spec generator as a **method inside `TimestampPlugin`** (before the
    class closing brace, only if absent).
- Normalise LLM output that contains literal `\n`/`\t` escape sequences before merging, so
  brace balancing and jest parsing stay clean.
- The spec contract wins: any LLM-emitted command/Modal with the contract id/name is stripped
  before the authoritative injection, guaranteeing exactly one correct instance.
- Omission guard preserved: merge output size must be `>=` existing size (no dropped logic).

## Capabilities

### New Capabilities
- `integrator-merge-refactor`: The integrator merges generated TS into `main.ts` via a
  deterministic anchor-based algorithm (no whole-file brace surgery) that honors the OpenSpec
  spec contract exactly, keeps existing logic, and produces tsc/rollup-clean output.

### Modified Capabilities
- `agentic-architecture-test-refactor`: this change is the concrete implementation of its
  task 5.1 ("merge, not replace") with a pinned, testable merge contract.

## Impact

- `agents/agentics/src/code_integrator_agent.py`: `integrate_code_deterministic`,
  `_assemble_contract_features`, and `_extract_balanced_blocks` rewritten.
- `agents/agentics/tests/unit/*`: new real unit test pinning the merge contract; broken tests
  fixed; reference-checked dead modules/tests removed.
- The `uuid-modal-agentic-generation` run then becomes a *verification* of this refactor.
