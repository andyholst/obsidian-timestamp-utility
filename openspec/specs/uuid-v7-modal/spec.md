# uuid-v7-modal Specification

## Purpose
TBD - created by archiving change uuid-modal-agentic-generation. Update Purpose after archive.
## Requirements
### Requirement: Register UUID v7 command as an Obsidian Modal
The plugin MUST implement the feature as an `obsidian.Modal` subclass (`UuidV7Modal`) and
register it as a command (id `insert-uuid-v7`, name "Insert UUID v7 (timestamp-based)") via
`this.addCommand({ id: "insert-uuid-v7", name: "...", callback: () => new UuidV7Modal(this.app).open() })`,
available from the Obsidian command palette. ALL generated TS features MUST follow this
Modal-as-command pattern (never a bare function).

#### Scenario: Command palette shows the new command
- **WHEN** the user opens the command palette
- **THEN** "Insert UUID v7 (timestamp-based)" is listed and selectable, and the registered callback opens the `UuidV7Modal` modal.

### Requirement: UUID v7 layout
The command MUST generate a UUID following the UUID v7 layout: 128-bit value, version bits (48–51) = `0111`, variant bits (64–65) = `10`.

#### Scenario: Generated value has correct version and variant
- **WHEN** a UUID is generated
- **THEN** the hex string has `7` in the version nibble (position 14) and `8|9|a|b` in the variant nibble (position 19).

### Requirement: Millisecond timestamp
The timestamp component MUST use a 48-bit millisecond Unix-epoch counter derived from the current system time.

#### Scenario: Timestamp is recent
- **WHEN** a UUID is generated
- **THEN** decoding the first 48 bits yields a Unix-ms time within a few seconds of `Date.now()`.

### Requirement: Secure randomness
The random components MUST be generated using a cryptographically secure RNG (e.g. `crypto.getRandomValues`).

#### Scenario: Two rapid invocations differ
- **WHEN** the command is invoked twice in the same millisecond
- **THEN** two distinct UUIDs are produced.

### Requirement: Canonical format
The UUID MUST be formatted as a 36-character hyphenated string: `xxxxxxxx-xxxx-7xxx-xxxx-xxxxxxxxxxxx`.

#### Scenario: Canonical format
- **WHEN** a UUID is generated
- **THEN** the output matches `^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`.

### Requirement: Insert at cursor
The generated UUID MUST be inserted at the current cursor position of the active Markdown editor.

#### Scenario: Insert at cursor
- **WHEN** the command runs with an active editor at a cursor offset
- **THEN** the UUID appears at the editor's cursor offset.

### Requirement: No active editor handling
When no active editor/note is present, the command MUST surface a Notice instead of throwing.

#### Scenario: No active editor
- **WHEN** the command runs with no Markdown view active
- **THEN** an Obsidian Notice is shown and no edit occurs.

