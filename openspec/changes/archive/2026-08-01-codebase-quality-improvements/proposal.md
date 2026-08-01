# Proposal: Codebase Quality Improvements

## Why

The codebase has accumulated several quality issues that affect maintainability, readability, and consistency:

1. **Misaligned indentation** in `src/main.ts` — the UUID v7 and Base64 command registrations use inconsistent indentation compared to the rest of the file, making it harder to read and maintain.
2. **Dead code methods** — `generateUuidV7()`, `encodeBase64()`, and `decodeBase64()` are defined as class methods but never called anywhere (the inline/modal implementations handle these cases).
3. **Tag regex limitation** in `src/taskProcessor.ts` — the regex `#\\w+` only matches single-word tags like `#tag` but not hyphenated tags like `#my-tag` which are valid Obsidian tags.
4. **Incomplete formatting coverage** — `.prettierrc.json` only formats `src/main.ts` and `src/__tests__/main.test.ts`, leaving `src/folderSelectorModal.ts`, `src/taskProcessor.ts`, and their test files unformatted.

## What Changes

- Fix indentation in `src/main.ts` for UUID v7 and Base64 command blocks (lines 153-192).
- Remove dead code methods: `generateUuidV7()`, `encodeBase64()`, `decodeBase64()` from `src/main.ts`.
- Update tag regex in `src/taskProcessor.ts` to support hyphenated tags.
- Expand `.prettierrc.json` formatting coverage to include all source and test files.

## Capabilities

- `codebase-quality`: Improved code quality across the entire plugin codebase.

## Impact

- **Low risk**: All changes are additive or cosmetic — no new behavior, no API changes.
- **Build/test**: Existing 65 tests pass; build succeeds. No test changes needed.
- **DX**: Cleaner code, consistent formatting, support for hyphenated tags in task processing.
- **No breaking changes**: Backward compatible with all existing functionality.
