# Tasks: loop-final — review-approved squash + changelog + force-push

## 1. Makefile: loop-final target
- [x] 1.1 Add `loop-final` target: guard `APPROVED=1` (else fail closed) + `BRANCH` required.
- [x] 1.2 `loop-final` runs `make loop-harness` FIRST and aborts non-zero if not green.
- [x] 1.3 On green + approved: `squash-commits` (bypass B28a/B30b only under this path) →
      `changelog` → `bump-from-changelog` → `changelog-format`.
- [x] 1.4 `git push --force-with-lease` the feature branch; refuse if branch is `main`/`origin/main`.
- [x] 1.5 Never call `git revert` (B30a stays absolute); force is `--force-with-lease` only.

## 2. B8 doc-sync (B32 across all sync files)
- [x] 2.1 AGENTS.md: add B32 durable behaviour block; bump B-range to B32.
- [x] 2.2 hermes/skills/openspec-loop-harness.md: mirror B32 + range bump.
- [x] 2.3 docs/openspec-engineering-loop-harness.md: add B32 row + range bump.
- [x] 2.4 scripts/run-loop-harness.sh: bump B-range comment.
- [x] 2.5 Makefile: add loop-final to .PHONY (target + comment carry B32).

## 3. Verification
- [x] 3.1 `openspec validate loop-final-reviewed-squash` passes.
- [x] 3.2 `make check-docs-sync` passes (all sync docs agree on B32 + stage order).
- [x] 3.3 `make loop-final` fails closed WITHOUT `APPROVED=1` (guard proven); also refuses main.
- [x] 3.4 Fast hermetic loop subset + FULL `make loop-harness` (B20 pre-flight) — ALL 10 STAGES GREEN.
