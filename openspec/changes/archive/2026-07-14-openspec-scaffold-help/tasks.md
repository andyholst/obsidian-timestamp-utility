# Tasks

- [x] 1.1 Create OpenSpec change `openspec-scaffold-help` via `openspec new change` (B15)
- [x] 2.1 Add a full `usage()` to `scripts/scaffold-openspec-change.sh` (SYNOPSIS / ARGUMENTS / two EXAMPLES / RESULT / NOTES); `-h`/`--help` prints it; missing `--name` prints error + usage
- [x] 2.2 Make `openspec-new` (Makefile) print the script `--help` when `NAME` is empty (not a bare one-line error)
- [x] 3.1 Verify help flag: `scripts/scaffold-openspec-change.sh --help` prints both EXAMPLE blocks and exits 0
- [x] 3.2 Verify missing-name path: `scripts/scaffold-openspec-change.sh` (no args) prints error + usage and exits non-zero
- [x] 4.1 VERIFICATION TASK (runs the command): `make openspec-new` with no NAME prints the usage/example text; assert by grepping output for `make openspec-new` and `EXAMPLE` (proves the documented help path is real, not prose-only)
- [x] 4.2 Regression check: `make openspec-new NAME=<probe>` still creates + validates a change (behaviour unchanged); remove the probe after
- [x] 5.1 `openspec validate openspec-scaffold-help` passes
