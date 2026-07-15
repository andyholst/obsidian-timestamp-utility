# Tasks

- [x] 1.1 Create OpenSpec change `record-work-script` (`openspec new change`) with proposal.md, specs/record-work/spec.md, this tasks.md
- [x] 2.1 Write `scripts/record-work.py`: parses change `proposal.md`/`tasks.md`/`specs/**`, runs `openspec status` + `openspec validate`, collects git branch + recent commit, invokes `hermes -z` (profile project-manager) to draft the prose, writes `agent-wiki/YYYY-MM-DD-<change>.md`, and appends a line to `agent-wiki/index.md`
- [x] 2.2 Script exits non-zero with a clear error when `openspec/changes/<name>` is absent (no file written)
- [x] 2.3 Script falls back to a deterministic stub body when `hermes -z` returns empty (never writes an empty body)
- [x] 3.1 Add `record-work` Makefile target: `b9-perms` prerequisite, invokes `scripts/record-work.py --change $(CHANGE) [--date $(DATE)]`, refuses when `CHANGE` empty
- [x] 4.1 B8-sync: update AGENTS.md Phase 7 to reference `make record-work CHANGE=<name>` / `scripts/record-work.py` (not a missing `record-work` skill)
- [x] 4.2 B8-sync: update `hermes/skills/openspec-loop-harness.md` to reference the same target/script
- [x] 5.1 Verify: run `make record-work CHANGE=record-work-script`, confirm `agent-wiki/2026-07-15-record-work-script.md` is written and `agent-wiki/index.md` gains a line
- [x] 6.1 `openspec validate record-work-script` passes
