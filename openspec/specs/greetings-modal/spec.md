# greetings-modal Specification

## Purpose
TBD - created by archiving change greetings-modal-agentic-generation. Update Purpose after archive.
## Requirements
### Requirement: Greetings command is registered
The plugin MUST register a command `insert-greetings` named `Show Greetings` that opens the modal.

#### Scenario: Command wired via addCommand
- **WHEN** the plugin loads (`onload()`)
- **THEN** `this.addCommand` registers id `insert-greetings` with name `Show Greetings`
- **AND** the command callback opens a `GreetingsModal`.

### Requirement: Greetings modal displays the greeting
The system MUST implement a `GreetingsModal` (an `obsidian.Modal` subclass) that, on open,
displays the text `Greetings command obsidian plugin`.

#### Scenario: Modal shows greeting on open
- **WHEN** the `GreetingsModal` is opened
- **THEN** its content element contains the text `Greetings command obsidian plugin`.

### Requirement: Behaviour is covered by tests
`src/__tests__/main.test.ts` MUST assert the command is registered with the correct id/name and
that opening the modal renders the greeting text.

#### Scenario: Tests assert registration and greeting
- **WHEN** the contract tests run
- **THEN** they confirm the `insert-greetings` command exists with name `Show Greetings`
- **AND** confirm the modal renders `Greetings command obsidian plugin`.

