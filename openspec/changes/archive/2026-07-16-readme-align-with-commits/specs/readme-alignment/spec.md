# readme-alignment Specification

## ADDED Requirements

### Requirement: README lists every currently registered plugin command
The README MUST enumerate all commands currently registered in `src/main.ts`. The plugin now
registers **nine** commands: `insert-timestamp`, `rename-with-timestamp`,
`rename-with-timestamp-title`, `rename-filename-with-title`, `insert-date-range`,
`insert-uuid-v7`, `encode-base64-message`, `decode-base64-message`, `process-tasks`. The README
intro count MUST match the real command count (nine, not six), and the three commands added after
the README's last update (`insert-uuid-v7`, `encode-base64-message`, `decode-base64-message`) MUST
appear in both the feature list and the Usage section.

#### Scenario: command count matches source
- **WHEN** a reader counts the commands described in the README
- **THEN** the count equals the number of `addCommand` calls in `src/main.ts` (nine)

#### Scenario: newly committed commands are documented
- **WHEN** the README is compared against the current `src/main.ts`
- **THEN** `insert-uuid-v7`, `encode-base64-message`, and `decode-base64-message` each have a Usage
  subsection and appear in the feature list

### Requirement: README Documentation section points at the loop/harness and AGENTS.md
The README Documentation section MUST reference the authoritative OpenSpec loop/harness technical
reference (`docs/openspec-engineering-loop-harness.md`) and the agent execution manual
(`AGENTS.md`), and MUST reference the `docs/architecture/` design docs, so a reader can locate the
harness-engineering + loop-engineering rules (durable behaviours B1–B25).

#### Scenario: loop/harness + AGENTS.md are referenced
- **WHEN** a reader opens the README Documentation section
- **THEN** it contains working links to `docs/openspec-engineering-loop-harness.md` and `AGENTS.md`

### Requirement: README describes only committed functionality
The README MUST NOT describe commands or behaviour that are not present in `src/main.ts`, and MUST
describe the newest committed functionality (the three commands above).

#### Scenario: no phantom commands
- **WHEN** each command described in the README is checked against `src/main.ts`
- **THEN** every described command has a matching `addCommand` in `src/main.ts`
