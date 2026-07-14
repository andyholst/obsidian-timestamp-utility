# Design — integrator-merge-refactor (Plan B)

## Goal
Replace the brittle whole-file brace-surgery merge with a small, deterministic, **anchor-based**
merge that is fully covered by a pinned unit test, so the loop self-corrects instead of
whack-a-mole-ing regex bugs.

## Algorithm (anchor-based)

1. **Normalise** LLM `new_code` / `new_tests`: replace literal `\\n` -> `\n`, `\\t` -> `\t`.
2. **Strip contract conflicts** from both the existing file and the LLM output:
   - remove any `this.addCommand({...})` block whose id == contract id,
   - remove any `class <ContractModal>` block (by name, any parent class).
   Use a *line-aware, brace-balanced* extractor that captures the full line (incl. `export`).
3. **Inject the authoritative contract command** into `onload()`:
   - find `onload()` / `async onload()` line, walk forward to its matching `}`, insert the
     spec command block (4-space indented) just before that `}`.
4. **Append the Modal** as a top-level class at file end if `class <Modal> extends obsidian.Modal`
   is absent.
5. **Append the generator** as a method inside `TimestampPlugin` if
   `^\s*(?:private\s+|public\s+)?generateX(` is absent:
   - find `export default class TimestampPlugin` line, brace-match to its closing `}`, insert
     the method just before that `}`.
6. **Imports**: append any `import` line from `new_code` not already present, after the import
   block.

## Why anchors, not whole-file brace counting
The previous `integrate_code_deterministic` counted braces across the *entire* file and inserted
"before the last `}`", which landed inside the appended Modal (placed at file end) instead of
inside the plugin class. Anchoring each insertion to its *specific* stable marker removes that
class of bugs. The generator and Modal are inserted at *different, explicit* anchors, so they
can never collide.

## Omission guard
`generate_updated_code_file` already falls back to LLM merge only if `len(merged) < len(existing)`.
Kept. The Makefile bash omission guard (timestamped backup, shrink -> restore) is unchanged.

## Test plan
- New `tests/unit/test_integrator_merge_unit.py`: asserts the 5 acceptance criteria above
  against the committed `main.ts` baseline (real logic; no Ollama/network/FS).
- Fix `tests/unit/test_test_suite_unit.py` broken relative import.
- Fix pytest/pytest-asyncio version mismatch (`asyncio_mode = auto` in pytest.ini).

## Dead-code removal
- Run an import-graph scan from `prod.agentics`; remove reference-checked orphan modules and
  their tests (keep allowlist: utils, exceptions, models, config, prompts, state, tools,
  clients, monitoring).
