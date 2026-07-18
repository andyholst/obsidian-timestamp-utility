## Why

The repo's Makefile routes every docker-compose backed target (build-app, test-app, run-agentics,
loop-*, deliver-change, phase7-archive, release-flow, ...) through $(call docker_run, ...), i.e.
the real HOST that owns the docker/nerdctl daemon + live Ollama. The foreground Hermes sandbox
(/workspace) has NO docker/nerdctl binary at all — it returns docker: command not found. AGENTS.md
already states that long-running make targets MUST be launched via terminal(background=true) so
they execute on the real host. In practice this rule is advisory: it is easy to forget, and nothing
enforces it, so a make ... run in the foreground silently dies on docker: command not found (or an
unattended long job is launched with no notification and its output is lost). We tighten the rule
into a hard, named behaviour so it is unambiguous and auditable, and extend the "background-only"
mandate to EVERY Makefile target that resolves a docker/nerdctl/compose binary — not just the long ones.

## What Changes

- Promote the existing "long-running make targets run via terminal(background=true)" guidance into a
  durable, numbered behaviour (B31) that is MANDATORY for ANY Makefile target that invokes a
  container runtime (docker / nerdctl / *compose*) — whether foreground or background sandbox.
- Clarify that the background-host channel is the ONLY supported path to the docker daemon; the
  foreground sandbox is never used for container-backed make targets.
- Add the behaviour to the B8 doc-sync set (AGENTS.md, hermes/skills/openspec-loop-harness.md,
  docs/openspec-engineering-loop-harness.md, Makefile, scripts/run-loop-harness.sh) so the B-range
  string is bumped B1-B30 -> B1-B31 consistently (preserves the check-docs-sync gate).
- No OpenSpec change dir is authored by hand — make openspec-new (the real openspec new change CLI)
  created this change (B15).

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- docker-make-pipeline: adds a REQUIREMENT that any Makefile target invoking a container runtime
  MUST be executed through terminal(background=true) (the real host), not the foreground sandbox.
  This is a behaviour-level change (new durable invariant), so it needs a delta spec file.

## Impact

- AGENTS.md, hermes/skills/openspec-loop-harness.md, docs/openspec-engineering-loop-harness.md,
  Makefile, scripts/run-loop-harness.sh — B-range bump + one tightened sentence.
- No Makefile target logic changes; this is a governance/behaviour clarification only.
- check-docs-sync (B8) must still PASS after the edits.
