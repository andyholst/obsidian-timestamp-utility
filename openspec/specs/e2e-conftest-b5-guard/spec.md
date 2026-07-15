# e2e-conftest-b5-guard Specification

## Purpose
TBD - created by archiving change e2e-conftest-b5-guard. Update Purpose after archive.
## Requirements
### Requirement: E2E harness guards same-file copies
The conftest MUST skip a `copy2` when the source and destination path are the same file (e.g.
`PROJECT_ROOT` equals the real repo root), to avoid `shutil.SameFileError`.

#### Scenario: PROJECT_ROOT equals real repo root
- **WHEN** the conftest would copy `package.json`/`tsconfig.json`/`jest.config.js`/`manifest.json`
  from the real root to a `PROJECT_ROOT` that is the same path
- **THEN** it skips the copy instead of raising `SameFileError`

