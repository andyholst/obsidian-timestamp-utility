# Tasks

- [x] 1.1 Create OpenSpec change `openspec-scaffold-make` via `openspec new change` (B15 — real CLI, not hand-written dir)
- [x] 2.1 Write `scripts/scaffold-openspec-change.sh`: invokes `openspec new change <NAME> [--description --goal]`, seeds `proposal.md` + `tasks.md` + `specs/<CAPABILITY>/spec.md` from a heredoc template, then runs `openspec validate <NAME>`
- [x] 2.2 Script refuses (non-zero) when `NAME` is empty; detects an existing change dir and refuses to overwrite
- [x] 2.3 Seeded `spec.md` uses the OpenSpec delta format (`## ADDED Requirements` → `### Requirement:` → `#### Scenario:` with `WHEN`/`THEN`); `openspec validate <NAME>` exits 0
- [x] 3.1 Add `openspec-new` Makefile target: `b9-perms` prerequisite; passes `NAME` (required), `DESC`, `GOAL`, `CAPABILITY` (default = NAME); refuses when `NAME` empty
- [x] 4.1 B8-sync: update AGENTS.md Phase 2 to reference `make openspec-new NAME=<name>` (or the script) as the canonical change-creation path
- [x] 4.2 B8-sync: update `hermes/skills/openspec-loop-harness.md` to reference the same target
- [x] 5.1 Verify: run `make openspec-new NAME=<probe> CAPABILITY=<probe>` on a throwaway name, confirm the CLI-created dir + seeded files exist and `openspec validate` passes, then remove the probe
- [x] 6.1 `openspec validate openspec-scaffold-make` passes
