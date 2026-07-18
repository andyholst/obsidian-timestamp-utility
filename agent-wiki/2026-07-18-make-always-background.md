# make-always-background — Work Log

**Date:** 2026-07-18
**OpenSpec Change:** `make-always-background`
**Branch:** `feat/make-always-background`

## Summary
This change promotes the existing advisory guidance ("long-running make targets run via terminal(background=true)") into a hard, numbered durable behaviour (B31) that is MANDATORY for ANY Makefile target invoking a container runtime — not just the long ones. It bumps the B-range string B1-B30 → B1-B31 across the entire B8 doc-sync set (AGENTS.md, hermes/skills/openspec-loop-harness.md, docs/openspec-engineering-loop-harness.md, Makefile, scripts/run-loop-harness.sh) and tightens the wording so the foreground sandbox (/workspace) is never a substitute for the host-owned docker/nerdctl daemon. The change is governance-only: no Makefile target logic changed, and it was authored through the real openspec new change CLI per B15.

## Verification Against Spec
- Requirement "Makefile docker-backed targets run through the background host": spec scenarios (long-running verify targets, any container-backed target, foreground-not-substitute) implemented by adding B31 wording in all 5 sync files; openspec validate produced no output (green) and tasks 3.1/3.2/4.1 confirm check-docs-sync + re-validation pass ✅
- Requirement "Background execution MUST be the default, not an opt-in": B31 recorded as MANDATORY DEFAULT in AGENTS.md + skill + docs + Makefile + run-loop-harness.sh (B1-B31 bump, tasks 2.1-2.5), and task 3.1 confirms each file's B-range agrees so check-docs-sync still PASSES ✅

## Key Decisions
- Bumped the B-range consistently B1-B30 → B1-B31 in EVERY occurrence (Makefile + docs each had multiple), not just the header, so check-docs-sync's B-range assertion stays green.
- Kept the change governance/behaviour-only: deliberately did NOT touch any $(call docker_run, ...) target logic, preserving the "no Docker/daggerer, no MCP, docker compose only" invariant from AGENTS.md.
- Clarified the mandate covers SHORT container-backed targets too (loop-collect, loop-ts-floor, loop-unit, test-agents-unit, test-agents-integration), closing the loophole where only "long-running" steps were assumed to need the background host.
- Authored the change dir exclusively via make openspec-new (real openspec new change CLI) — no hand-written directory — to satisfy B15, and task 3.3 confirms no hand-authored change dir and an otherwise-unchanged working tree.

## Current Status
Complete — all tasks ticked, openspec validate green, and make check-docs-sync passes with the B1-B31 range agreed across the sync set.

## Recommended Next Steps
None — archive.
