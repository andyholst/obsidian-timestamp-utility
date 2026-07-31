# Tasks: Codebase Quality Improvements

## Contract
- `src/main.ts` must have consistent 4-space indentation for all command registrations
- Dead code methods (`generateUuidV7`, `encodeBase64`, `decodeBase64`) must be removed from `src/main.ts`
- `src/taskProcessor.ts` tag regex must support hyphenated tags (e.g., `#my-tag`)
- `.prettierrc.json` must format all `.ts` files in `src/` and `src/__tests__/`

## Test Contract
- All 65 existing tests must pass (`npm test`)
- Build must succeed (`npm run build`)
- TypeScript validation must pass (`npx tsc --noEmit`)

## Tasks

- [ ] 1. Fix indentation in `src/main.ts` for UUID v7 and Base64 command blocks (lines 153-192)
- [ ] 2. Remove dead code methods: `generateUuidV7()`, `encodeBase64()`, `decodeBase64()` from `src/main.ts`
- [ ] 3. Update tag regex in `src/taskProcessor.ts` line 10 to support hyphenated tags
- [ ] 4. Expand `.prettierrc.json` formatting coverage to include all source and test files
- [ ] 5. Run `npm run build` and confirm exit 0
- [ ] 6. Run `npm test` and confirm all tests pass
- [ ] 7. Run `npx tsc --noEmit` and confirm no TypeScript errors
- [ ] 8. Verify changes with `git diff` and review for correctness
- [ ] 9. openspec validate codebase-quality-improvements passes
