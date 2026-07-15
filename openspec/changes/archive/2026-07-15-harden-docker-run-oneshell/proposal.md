# Harden docker_run under .ONESHELL + fix RECORD_WORK_CMD git PATH

## Why
The Makefile sets `.ONESHELL:` (all of a target's recipe lines run in ONE shell). The
`docker_run` macro ended with a bare `exit $$_rc`, which exited that shared shell and
**silently dropped every subsequent recipe line** while still reporting exit 0. This broke
any target that runs a `docker_run` and then more lines — notably `record-work` /
`phase7-archive` (the host `hermes -z` step and the container write step never ran) and
`regen-doc-sync-fixtures` / `loop-collect` (second container call skipped). Separately,
`RECORD_WORK_CMD` used `export PATH=/project/node_modules/.bin:$PATH`, which clobbered
`/usr/bin` in some layers and produced `git: not found`, so the emitted work-log lost its
git metadata and prose.

## What Changes
- `docker_run` no longer ends with unconditional `exit`; it exits **only on non-zero**
  (`if [ $$_rc -ne 0 ]; then exit $$_rc; fi`) so success continues to the next recipe line.
- The non-tty branch keeps the `script -qec "/bin/sh <heredoc-tmpfile>" /dev/null` PTY wrap
  (nerdctl hardcodes `--tty`, has no `-T`; heredoc preserves the command's inner quotes).
- `RECORD_WORK_CMD` uses a LITERAL absolute PATH including `/usr/bin` (git) +
  `/project/node_modules/.bin` (openspec) instead of `$PATH`-derived.
- `build-app` and `test-app` now go through `docker_run` (they were raw `docker compose run`
  and silently no-op'd under non-tty — "provided file is not a console" — while reporting
  success; a false green in the loop's build/test gates).

## Capabilities
- docker-run: deterministic multi-line recipe execution through `docker_run` under
  `.ONESHELL` in both tty and non-tty/piped/background contexts, with failure propagation.

## Impact
- `Makefile` (`docker_run` macro, `RECORD_WORK_CMD`).
- All `$(call docker_run,...)` targets; especially multi-call ones: `record-work`,
  `record-work-prompt`, `phase7-archive`, `regen-doc-sync-fixtures`, `loop-collect`.
- No generated TS. No git commit/push (B4/B14).
