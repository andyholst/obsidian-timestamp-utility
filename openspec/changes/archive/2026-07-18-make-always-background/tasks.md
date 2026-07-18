## 1. Sync the OpenSpec change + B8 docs

- [x] 1.1 Create this change via the real openspec new change CLI (make openspec-new NAME=make-always-background) — done, do not hand-author (B15)
- [x] 1.2 Write proposal.md, specs/docker-make-pipeline/spec.md (delta: MODIFIED + ADDED requirements), and this tasks.md
- [x] 1.3 Run openspec validate make-always-background and confirm it is green

## 2. Bump + tighten the B-range across the B8 sync set

- [x] 2.1 In AGENTS.md, add behaviour B31 (background-host mandatory for docker-backed make targets) and bump its B-range string B1-B30 -> B1-B31
- [x] 2.2 In hermes/skills/openspec-loop-harness.md, bump B1-B30 -> B1-B31 and add the same B31 wording
- [x] 2.3 In docs/openspec-engineering-loop-harness.md, bump B1-B30 -> B1-B31 (all occurrences) and add B31 wording
- [x] 2.4 In Makefile, bump B1-B30 -> B1-B31 (all occurrences)
- [x] 2.5 In scripts/run-loop-harness.sh, bump B1-B30 -> B1-B31

## 3. Verify the sync gate + change

- [x] 3.1 Run make check-docs-sync (host, via terminal(background=true)) and confirm it PASSES (stage order, ts-floor guard, and B-range all agree)
- [x] 3.2 Re-run openspec validate make-always-background — green
- [x] 3.3 Confirm git status shows no hand-authored change dir and the working tree is otherwise unchanged

## 4. Final verification (loops back to spec)

- [x] 4.1 openspec validate make-always-background passes with all artifacts complete
