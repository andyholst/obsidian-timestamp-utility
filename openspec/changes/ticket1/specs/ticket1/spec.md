# Capability: feat-added-timestamp-commands-for-obsidian-notes

Implement the behaviour requested by the source GitHub issue as a new Obsidian command.

## ADDED Requirements

### Requirement: Register the command as an Obsidian Modal
The plugin MUST implement the feature as an `obsidian.Modal` subclass and register it as a command via `this.addCommand({...})`, available from the command palette.

#### Scenario: Command is available
- **WHEN** the user opens the command palette
- **THEN** the new command is listed and selectable.

### Requirement: Insert at cursor
The generated value MUST be inserted at the current cursor position of the active Markdown editor.

#### Scenario: Insert at cursor
- **WHEN** the command runs with an active editor
- **THEN** the value appears at the editor's cursor offset.

## ADDED Acceptance Criteria

- `npm run build` (tsc/rollup) compiles with no error.
- `npm test` (jest) passes for `main.test.ts`.
