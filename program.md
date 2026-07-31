# program.md — Free-reign AutoResearch on Obsidian Timestamp Utility

You are running an autonomous research loop with **maximum freedom**.
Your only job is to make this repository better — more correct, more robust, higher coverage, simpler, fewer edge-case bugs, better DX.

You have free reign. You may try almost anything.
The only hard requirement is this:

> Every direction that actually improves the repo (or looks strongly promising) **must** be captured as a proper OpenSpec change so it can later be executed through the normal AGENTS.md + loop-harness pipeline.

You are not allowed to just leave a pile of experimental commits. Successful or high-potential work must be turned into OpenSpec artifacts.

---

## Core Rules

### Free reign (what you *can* do)
- Explore any part of the plugin (`src/`, tests, Makefile targets related to the app, configs, edge cases, missing validations, UX of commands, etc.)
- Try radical simplifications, stronger error handling, better coverage, new helpful commands, better date/UUID/reminder handling, etc.
- Break things temporarily while exploring
- Run any combination of `make test-app`, `make build-app`, `make loop-harness`, coverage reports, manual checks
- Create temporary experimental branches / worktrees for wild ideas
- Measure improvement however makes sense (test pass rate, coverage %, fewer crashes, cleaner code, etc.)

### Hard constraints (what you *must* respect)
1. **Never** permanently damage `main` or the production agentic pipeline under `agents/`.
2. Successful / promising work **must** be formalized as OpenSpec changes.
3. Prefer creating proper OpenSpec changes early rather than accumulating lots of experimental noise.
4. When formalizing, use the real CLI:
   ```bash
   make openspec-new NAME=<kebab-name> [CAPABILITY=...] [DESC="..."] [GOAL="..."]
   ```
5. After creating the OpenSpec change, fill in high-quality:
   - `proposal.md` (Why / What / Impact)
   - `tasks.md`
   - `specs/<capability>/spec.md` (proper delta format with Requirements + Scenarios)
6. You may leave experimental work on `wt/<name>` or `autoresearch/...` branches, but the OpenSpec change is the real deliverable.

---

## Recommended Operating Loop

1. **Survey**
   - Read the current state of `src/main.ts`, tests, recent commits, any failing tests, coverage gaps, and known pain points.
   - Identify 3–7 concrete improvement opportunities (bugs, missing edge cases, weak coverage, complexity, missing features, etc.).

2. **Explore freely**
   - Pick one idea.
   - Create an experimental branch or worktree if useful.
   - Implement and test aggressively.
   - Measure whether it actually improved something.

3. **Decide**
   - Clear improvement or high potential → formalize as OpenSpec change **now**.
   - Dead end or too messy → discard / reset and move on.
   - Interesting but incomplete → still create a lightweight OpenSpec change that captures the direction and remaining work.

4. **Formalize (mandatory for good ideas)**
   ```bash
   make openspec-new NAME=<good-kebab-name> DESC="..." GOAL="..."
   ```
   Then write a solid `proposal.md`, `tasks.md`, and proper `spec.md` with Requirements + Scenarios so the normal harness can later execute it cleanly.

5. **Log progress**
   Keep a simple running log (e.g. `research-log.md` or `results.tsv`) of:
   - What you tried
   - What improved / what didn’t
   - Which OpenSpec changes you created

6. **Never stop**
   Keep cycling through ideas. Prefer depth on high-leverage improvements over random thrashing. When you run out of obvious ideas, go looking for subtler ones (edge cases in date ranges, reminder conversion, UUID v7 monotonicity, file renaming safety, test gaps, etc.).

---

## Success Criteria

You are succeeding when:
- Real improvements land (higher coverage, fewer bugs, cleaner code, stronger edge-case handling)
- Those improvements are not just left as experimental commits — they exist as well-formed OpenSpec changes that the normal AGENTS.md pipeline can pick up and drive to completion
- The repo is in a better state than when you started, and the path forward is clearly specified in OpenSpec form

---

## Starting instruction

Begin by reading the current codebase and this file.
Then start exploring with free reign.
Whenever something is worth keeping, turn it into an OpenSpec change immediately.

Go.
