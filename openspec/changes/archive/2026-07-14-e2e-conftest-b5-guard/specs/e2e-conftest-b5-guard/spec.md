## ADDED Requirements
### Requirement: E2E harness never deletes the real committed source
The e2e conftest MUST NOT `rmtree` or `copytree` INTO the real plugin `src/` (the committed
baseline) under any `PROJECT_ROOT`. Generation must occur only in an isolated temp dir.

#### Scenario: PROJECT_ROOT is the real repo root
- **WHEN** the conftest resolves `PROJECT_ROOT` to the real plugin repo (so `PROJECT_ROOT/src`
  equals the real committed `src/`)
- **THEN** it does NOT delete or overwrite the real `src/`; it skips the copy and reads the real
  source directly

#### Scenario: PROJECT_ROOT is an isolated temp dir
- **WHEN** `PROJECT_ROOT` is an isolated temp directory (e.g. `/tmp/obsidian-project-xyz`)
- **THEN** the conftest may rmtree+copy the real `src/` into that temp dir for generation

## ADDED Requirements
### Requirement: E2E harness guards same-file copies
The conftest MUST skip a `copy2` when the source and destination path are the same file (e.g.
`PROJECT_ROOT` equals the real repo root), to avoid `shutil.SameFileError`.

#### Scenario: PROJECT_ROOT equals real repo root
- **WHEN** the conftest would copy `package.json`/`tsconfig.json`/`jest.config.js`/`manifest.json`
  from the real root to a `PROJECT_ROOT` that is the same path
- **THEN** it skips the copy instead of raising `SameFileError`
