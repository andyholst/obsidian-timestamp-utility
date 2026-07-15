# Tasks — doc-sync-gate

- [x] 1.1 Scaffold `scripts/check-docs-sync.py` that compares canonical B8 tokens across all sync files
- [x] 1.2 Canonical tokens: 8-stage order string (with `loop-ts-floor`), `loop-ts-floor` token, B-range upper bound (B25)
- [x] 1.3 Exit 0 when all sync files agree; print `DOC-SYNC: PASS`
- [x] 1.4 Exit non-zero when any file drifts; print each offending file + which token drifted
- [x] 2.1 Integrate Hermes CLI on drift: `hermes profile use project-manager` then `hermes -z "<drift prompt>"`
- [x] 2.2 Scope Hermes call to the current working directory (cwd = where command is asked); tolerate Hermes absence (still exit non-zero)
- [x] 3.1 Add `make check-docs-sync` target (hermetic, no network/Ollama)
- [x] 3.2 Wire `check-docs-sync` into `loop-collect` so drift fails the hermetic pre-flight
- [x] 4.1 Fix drifted `docs/openspec-engineering-loop-harness.md`: 7→8 stages + add `loop-ts-floor` (B8 alignment)
- [x] 5.1 TEST: run `make check-docs-sync` — expect PASS (green)
- [x] 5.2 TEST: force a drift (temporarily edit a sync file) — expect non-zero + Hermes prompt fires + offending file printed; restore
- [x] 5.3 TEST: run `make check-docs-sync` from a non-root subdir (e.g. `docs/`) — confirm Hermes cwd is that subdir (per-path scoping)
- [x] 6.1 `openspec validate doc-sync-gate` passes
- [x] 6.2 B8-sync: update AGENTS.md + skill four-artifact block to name `docs/openspec-engineering-loop-harness.md` as a sync'd file
- [x] 7.1 VERIFY: `make loop-collect` runs `check-docs-sync` as a sub-step and exits non-zero on drift
- [x] 8.1 Archive change (`make phase7-archive CHANGE=doc-sync-gate`) — B16 open-task guard + B1 e2e retained
- [x] 8.2 Write agent-wiki entry + update index
