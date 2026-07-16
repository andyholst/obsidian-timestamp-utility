# Tasks — readme-align-with-commits

- [x] 1.1 Update README intro: "six convenient commands" -> "nine convenient commands"; add
  `insert-uuid-v7`, `encode-base64-message`, `decode-base64-message` to the feature list with
  one-line descriptions matching their behaviour in `src/main.ts`.
- [x] 2.1 Add a Usage subsection "Insert UUID v7" documenting the timestamp-based UUID v7 insertion
  at the cursor (`id: insert-uuid-v7`, no modal).
- [x] 2.2 Add a Usage subsection "Encode Base64 Message" documenting the Base64 encode modal (textarea
  input + Encode button, result shown in the modal; `id: encode-base64-message`).
- [x] 2.3 Add a Usage subsection "Decode Base64 Message" documenting the Base64 decode modal
  (`id: decode-base64-message`).
- [x] 3.1 Verify the Documentation section references `docs/openspec-engineering-loop-harness.md` +
  `AGENTS.md` (working links) and note the `docs/openspec-loop-harness-guide.md` redirect; fix any
  stale link.
- [x] 4.1 Assert README<->`src/main.ts` parity: all 9 `addCommand` ids present in README
  (verified against friendly command names; README claims "nine convenient commands").
- [x] 5.1 `openspec validate readme-align-with-commits` passes.
