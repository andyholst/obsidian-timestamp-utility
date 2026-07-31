# Spec: Codebase Quality

## ADDED Requirements
### Requirement: Consistent Indentation in main.ts
The system MUST have consistent 4-space indentation for all command registrations in `src/main.ts`.

#### Scenario: UUID v7 command indentation
- **WHEN** the UUID v7 command is registered in `src/main.ts`
- **THEN** it uses consistent 4-space indentation matching other command registrations

#### Scenario: Base64 commands indentation
- **WHEN** the Base64 encode/decode commands are registered in `src/main.ts`
- **THEN** they use consistent 4-space indentation matching other command registrations

### Requirement: No Dead Code Methods
The system MUST NOT have unused class methods in `src/main.ts`.

#### Scenario: generateUuidV7 removed
- **WHEN** the plugin code is analyzed
- **THEN** the `generateUuidV7()` method is not present (inline implementation handles UUID generation)

#### Scenario: encodeBase64 removed
- **WHEN** the plugin code is analyzed
- **THEN** the `encodeBase64()` method is not present (Base64Modal handles encoding)

#### Scenario: decodeBase64 removed
- **WHEN** the plugin code is analyzed
- **THEN** the `decodeBase64()` method is not present (Base64Modal handles decoding)

### Requirement: Hyphenated Tag Support
The system MUST support hyphenated tags in task processing.

#### Scenario: Single-word tag
- **WHEN** a reminder line contains `#tag`
- **THEN** it is matched by the regex

#### Scenario: Hyphenated tag
- **WHEN** a reminder line contains `#my-tag`
- **THEN** it is matched by the regex

#### Scenario: Multiple hyphenated tags
- **WHEN** a reminder line contains `#project-alpha`
- **THEN** it is matched by the regex

### Requirement: Complete Formatting Coverage
The system MUST format all TypeScript source and test files.

#### Scenario: All source files formatted
- **WHEN** prettier runs via `npm run build`
- **THEN** all `.ts` files in `src/` are formatted

#### Scenario: All test files formatted
- **WHEN** prettier runs via `npm run build`
- **THEN** all `.ts` files in `src/__tests__/` are formatted
