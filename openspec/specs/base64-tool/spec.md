# base64-tool Specification

## Purpose
TBD - created by archiving change base64-tool. Update Purpose after archive.
## Requirements
### Requirement: Base64 encode command
The system MUST provide an Obsidian command with id `encode-base64-message` named
`Encode Base64 Message` that opens a `Base64Modal`. The modal MUST accept a plaintext message and,
when the user confirms, display the base64-encoded form of that message.

#### Scenario: User encodes a message
- **WHEN** the user runs the `Encode Base64 Message` command and enters `hello world`
- **THEN** the modal displays `aGVsbG8gd29ybGQ=`

#### Scenario: Generated code honors the contract
- **WHEN** the agentic pipeline integrates the change
- **THEN** `src/main.ts` contains exactly one `Base64Modal` class and exactly one
  `encode-base64-message` command, and the encoded output equals `btoa`-style base64 of the input.

### Requirement: Base64 decode command
The system MUST provide an Obsidian command with id `decode-base64-message` named
`Decode Base64 Message` that opens the same `Base64Modal` in decode mode. The modal MUST accept a
base64 string and, when the user confirms, display the decoded plaintext.

#### Scenario: User decodes a message
- **WHEN** the user runs the `Decode Base64 Message` command and enters `aGVsbG8gd29ybGQ=`
- **THEN** the modal displays `hello world`

#### Scenario: Invalid base64 shows a Notice
- **WHEN** the user runs the `Decode Base64 Message` command and enters `not base64!!!`
- **THEN** the modal shows an error `obsidian.Notice` and does not crash.

### Requirement: Deterministic contract floor injection
The `CodeIntegratorAgent` deterministic floor MUST inject the `## Contract` / `## Test Contract`
TypeScript from this change's `tasks.md` verbatim (parsed by the `=== CONTRACT_* ===` /
`=== TEST_CONTRACT_* ===` markers). No generated TS bodies may live in Python (B10/B11).

#### Scenario: Contract markers present and injected
- **WHEN** the pipeline runs against this change
- **THEN** the generated `src/main.ts` contains `encode-base64-message`, `decode-base64-message`,
  the `Base64Modal` class, and the `encodeBase64` / `decodeBase64` generator methods; and the
  generated `src/__tests__/main.test.ts` contains contract tests exercising both commands.

