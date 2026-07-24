# readme-docs Specification

## Purpose
Two readme-docs changes under one capability. (1) Added a `## Documentation` section to `README.md`
mapping contributors to `docs/AGENTIC_ARCHITECTURE.md`, `docs/architecture/`,
`docs/openspec-engineering-loop-harness.md`, and `AGENTS.md` (post-reorganization paths). (2)
Corrected `README.md` to match the real repo: removed the false MCP claim (localhost:3003 /
`make start-mcp-persist`), fixed `make run-agentics` to `CHANGE=<name>` (local OpenSpec change, no
GitHub fetch) dropping the non-existent `build-image-agents` / `agentics.log`, fixed test
references to `agents/agentics/tests/{unit,integration}`, and corrected llama model defaults to
`qwen3.6-35b-a3b`. README format/headings preserved. Verified via
`make loop-collect` + `make loop-unit`. README-only — no B8 behaviour change.
## Requirements
### Requirement: README documents the documentation layout
`README.md` MUST contain a `## Documentation` section that maps contributors to the repository's
documentation, linking (with correct relative paths) to `docs/AGENTIC_ARCHITECTURE.md`,
`docs/architecture/`, `docs/openspec-engineering-loop-harness.md`, and `AGENTS.md`, and MUST NOT
link to removed/moved paths (`docs/ARCHITECTURE_REFACTOR.md`, `agents/agentics/*.md`).

#### Scenario: documentation section present and correct
- **WHEN** a contributor opens `README.md`
- **THEN** a `## Documentation` section exists with working relative links and one-line
  descriptions, and no link points at removed/moved paths.

### Requirement: README links use post-reorganization paths
Every documentation link in `README.md` MUST use the current layout
(`docs/AGENTIC_ARCHITECTURE.md`, `docs/architecture/...`, `docs/openspec-engineering-loop-harness.md`,
`AGENTS.md`). No link may reference the removed `ARCHITECTURE_REFACTOR.md` or the old
`agents/agentics/` doc locations.

#### Scenario: no stale doc links in README
- **WHEN** `README.md` is grepped for documentation references
- **THEN** it contains no link to `ARCHITECTURE_REFACTOR.md` or `agents/agentics/*.md`, and all
  linked doc files exist at the referenced paths.

### Requirement: Documentation change does not regress the agentic suite
Because this change touches only `README.md`, it MUST NOT alter any Python source, Makefile, or
import path, and the hermetic agentic gates MUST remain green.

#### Scenario: hermetic gates still pass
- **WHEN** `make loop-collect` and `make loop-unit` run after the README edit
- **THEN** they pass (no Python source changed).

### Requirement: README run instructions match the real Makefile
The "Running the Ticket Interpreter Agent" (agentic pipeline) section MUST describe the actual
command: `make run-agentics CHANGE=<openspec-change-name>` runs the pipeline against a LOCAL
OpenSpec change (no GitHub fetch, no MCP). It MUST NOT instruct the user to run a non-existent
`make build-image-agents` target, reference an `ISSUE_URL=` invocation, or mention an
`agentics.log` file that is not produced.

#### Scenario: run-agentics documented correctly
- **WHEN** a contributor follows the README "Steps to Run the Agent"
- **THEN** it uses `make run-agentics CHANGE=<name>`, says it runs on a local OpenSpec change, and
  contains no `build-image-agents`, `ISSUE_URL=`, or `agentics.log` references.

### Requirement: README contains no false MCP requirement
The README MUST NOT claim that integration tests or the agentics pipeline require an MCP server
(e.g. "persistent MCP server on localhost:3003" / `make start-mcp-persist`). The system runs via
docker compose only (no MCP), per `AGENTS.md`.

#### Scenario: no MCP claim in README
- **WHEN** the README is grepped for MCP / localhost:3003 / start-mcp-persist
- **THEN** no such text is present.

### Requirement: README test references point at the real layout
The "Running the Tests" section MUST reference the actual test tree
(`agents/agentics/tests/unit/` and `agents/agentics/tests/integration/`) and the real Makefile
targets (`make test-agents-unit`, `make test-agents-integration`, `make test-agents`). It MUST NOT
name non-existent files like `test_ticket_interpreter.py`.

#### Scenario: test section accurate
- **WHEN** the README "Running the Tests" section is read
- **THEN** it references the `agents/agentics/tests/{unit,integration}` directories and the real
  `make test-agents*` targets, with no invented filenames.

### Requirement: README env defaults match the Makefile
The documented llama model defaults MUST match the Makefile (`LLAMA_MODEL` /
`LLAMA_CODE_MODEL` default to `qwen3.6-35b-a3b`; `LLAMA_HOST` defaults to
`http://localhost:11434`).

#### Scenario: model defaults correct
- **WHEN** the README Prerequisites list llama env vars
- **THEN** the stated defaults equal the Makefile values (not `qwen3.5:9b` / `qwen3.5:4b`).

### Requirement: Documentation change preserves format and does not regress the agentic suite
The README edit MUST keep its existing heading structure and bullet/code-fence style, touch only
`README.md`, and MUST NOT alter any Python source, Makefile, or import path. The hermetic agentic
gates MUST remain green.

#### Scenario: hermetic gates still pass
- **WHEN** `make loop-collect` and `make loop-unit` run after the README edit
- **THEN** they pass (no Python source changed).

