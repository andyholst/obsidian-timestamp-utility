# openspec-scaffold-help Specification

## ADDED Requirements

### Requirement: Script prints documented usage with examples
`scripts/scaffold-openspec-change.sh` MUST provide a `usage()` that documents the SYNOPSIS,
ARGUMENTS (`--name` required, `--desc`/`--goal`/`--capability` optional, `-h/--help`), two worked
EXAMPLES (direct invocation and via `make openspec-new`), the RESULT (files produced + validate
step), and NOTES (B4/B14, overwrite guard). Running the script with `-h`/`--help`, or with no
`--name`, MUST print this usage (and exit non-zero when `--name` is missing).

#### Scenario: help flag
- **WHEN** `scripts/scaffold-openspec-change.sh --help` (or `-h`) runs
- **THEN** it prints the full usage text including both EXAMPLE blocks and exits 0.

#### Scenario: missing name prints usage
- **WHEN** the script runs with no `--name`
- **THEN** it prints an error naming the required argument and the usage text, and exits non-zero.

### Requirement: Makefile surfaces the same help
The `openspec-new` Makefile target MUST, when invoked with no `NAME`, print the script's usage
(including the worked examples) rather than a bare one-line error, so the user sees how to pass
arguments. A successful invocation (NAME provided) MUST still create the change via the openspec
CLI and validate it.

#### Scenario: make openspec-new with no NAME
- **WHEN** `make openspec-new` runs with no `NAME`
- **THEN** it prints the script usage (with the `make openspec-new NAME=...` example) and exits
  non-zero, writing no change directory.

#### Scenario: make openspec-new with NAME still works
- **WHEN** `make openspec-new NAME=<name> [CAPABILITY=<cap>] ...` runs
- **THEN** it creates + validates the change exactly as before (behaviour unchanged).

### Requirement: Help behaviour is verified through make
The change's `tasks.md` MUST contain a verification task that actually runs `make openspec-new`
(with no NAME) and asserts the usage text appears (e.g. the `EXAMPLE` / `make openspec-new`
string), proving the help path works — not just asserting it in prose.

#### Scenario: verification task runs the command
- **WHEN** the verification task executes `make openspec-new` (no NAME) and greps the output for
  the usage/example markers
- **THEN** the assertion passes (usage present), confirming the documented behaviour is real.
