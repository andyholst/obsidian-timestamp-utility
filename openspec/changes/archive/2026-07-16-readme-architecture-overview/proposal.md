# Proposal: README Architecture Overview

## Why
The repository is a **two-sided system**: (1) an Obsidian community plugin written in
TypeScript (`src/main.ts` + `src/*.ts`, nine registered commands) that runs inside
Obsidian, and (2) a Python **agentic pipeline** (`agents/agentics/`) that reads an
OpenSpec change and deterministically generates that plugin's TypeScript + tests, all
gated by the OpenSpec loop/harness (`docs/openspec-engineering-loop-harness.md`).

A new reader opening `README.md` today gets a thorough but *command-by-command* guide to
the plugin and then, further down, a "Ticket Interpreter Agent" section — but no single
**helicopter-view** paragraph that explains what this repository *is* and how the two
halves relate. The README's Documentation section links to `docs/AGENTIC_ARCHITECTURE.md`,
but that document only describes the Python pipeline half in depth; it never frames the
whole system (plugin ↔ pipeline ↔ OpenSpec loop) or how the parts fit together. As a
result the README and the architecture doc are "linked" in the narrow sense (a hyperlink
exists) but the architecture doc does not represent the system as a whole, and the README
gives no high-level mental model.

This change closes both gaps: it adds a top-level overview to the README (so a person
understands the project from 30,000 feet) and expands the architecture document so it
represents the entire system in detail — the plugin surface, the agentic generator, and
the OpenSpec loop that binds them.

## What Changes
- **README**: insert a "What this project is" overview section (right after the title)
  that frames the two-sided system in one screen — the Obsidian plugin (what the user
  gets) and the agentic code-generation pipeline + OpenSpec loop (how it is built/maintained).
  Keep the existing detailed command list and per-command Usage sections as the
  "ground-level" detail. Make the existing Architecture link prominent and accurate.
- **Architecture doc** (`docs/AGENTIC_ARCHITECTURE.md`): expand it from a
  Python-pipeline-only reference into a full-system architecture document:
  - a system-level overview (the two halves + the OpenSpec loop that connects them);
  - the **plugin** surface in detail (the nine commands, their `id`s, modals, file layout
    `src/*.ts`, build via rollup → `dist/main.js`);
  - the **agentic pipeline** (kept from the current doc: entry points, module/agent map,
    three-phase workflow, deterministic merge floor, test layout);
  - the **OpenSpec loop/harness** as the coordinating discipline (generate → verify →
    archive), with a pointer to the authoritative harness reference.
- No TypeScript or Python source is changed — documentation only.

## Capabilities
- `readme-architecture-overview` (new): the README presents a helicopter-view system
  overview and links clearly to an architecture document that represents the whole
  two-sided system (plugin + agentic pipeline + OpenSpec loop) in detail.

## Impact
- Docs-only change; no generated TS, no agent behaviour change. The deterministic floor
  (B10/B11) and the no-commit/no-push gate (B4/B14) are unaffected and MUST NOT regress.
- The README is **not** part of the B8 four-file doc-sync set, so `make check-docs-sync`
  is not the gate. The gates are: README links to a system-level architecture doc that
  exists and is internally consistent, `docs/AGENTIC_ARCHITECTURE.md` describes the
  plugin surface and the loop (not just the Python pipeline), and `openspec validate`
  is green.
