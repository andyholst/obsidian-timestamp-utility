# Tasks

## fix + verify (body sectionized + idempotent)
- [x] 1.1 `gen_changelog.sh` renders `## Unreleased` from `git log <latest-tag>..HEAD`, parsing each
      commit's subject for the Conventional-Commit type and rendering the commit BODY as indented
      sub-bullets under the SAME type section.
      VERIFY: a `fix:` commit's body bullets appear under `### 🐞 Bug Fixes`. ✅ DONE (verified on
      squashed `18a6f6b`).
- [x] 1.2 `merge_changelog.py` overwrites the working `## Unreleased` (renames `<tag> Latest` →
      `Unreleased`), never re-adds released versions, and collapses duplicate group headers.
      VERIFY: output has exactly one `## Unreleased`; each group heading appears once. ✅ DONE.
- [x] 1.3 `docker_run` no longer passes inline paths to `script` (was `script: cannot open /project`).
      VERIFY: `make changelog` runs both `changelog` + `changelog-format` with exit 0. ✅ DONE.
- [x] 1.4 Idempotent: restore-to-main + `make changelog` 3x yields byte-identical `## Unreleased`
      (md5 hash stable); 2 extra runs without restore keep `## Unreleased` count == 1, no dupes.
      VERIFY: hashes matched across 3 runs; stacking runs did not duplicate. ✅ DONE.

## alignment with the squashed commit
- [x] 2.1 `## Unreleased` reflects exactly the squashed commit(s) in `0.4.10..HEAD`, grouped by type,
      with the commit body sectionized under the matching type section.
      VERIFY: `grep -A12 '### 🐞 Bug Fixes' CHANGELOG.md` shows the squashed `fix(...)` subject + body. ✅ DONE.
- [x] 2.2 Excludes off-branch / leaked probe commits (`feat(proof)`, `feat: test`, `feat: wip`).
      VERIFY: `grep -cE 'feat\(proof\)|feat: test|feat: wip' CHANGELOG.md` == 0. ✅ DONE.

## baseline + idempotency
- [x] 3.1 Restore to `origin/main` baseline (top `## 0.4.9`, no `## Unreleased`), then `make changelog`
      regenerates one clean `## Unreleased`. VERIFY: repeated restore + run yields identical output. ✅ DONE.

## verification
- [x] 4.1 `openspec validate changelog-sections-from-commit-type` passes.
