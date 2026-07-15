# Tasks — harden-docker-run-oneshell

## 1. Implementation (already applied)
- [x] 1.1 `docker_run` macro ends with `if [ $$_rc -ne 0 ]; then exit $$_rc; fi` (no bare `exit`)
- [x] 1.2 `RECORD_WORK_CMD` uses literal PATH incl `/usr/bin` + `/project/node_modules/.bin`
- [x] 1.3 Temporary `zztest` diagnostic target removed from Makefile
- [x] 1.4 `build-app` + `test-app` routed through `docker_run` (were raw `docker compose run` —
        false-green under non-tty: printed "Build complete" while the container never ran)

## 2. Verify affected SINGLE-docker_run targets run green
- [x] 2.1 `make loop-unit` — unit tests in container (RC=0, 525 passed)
- [x] 2.2 `make lint-python` — ruff check via docker_run (RC=0, ran to completion)
- [x] 2.3 `make check-docs-sync` — B8 gate single docker_run (RC=0, PASS)
- [x] 2.4 `make test-check-docs-sync` — doc-sync pytest in container (RC=0)

## 3. Verify affected MULTI-docker_run targets run ALL lines (the .ONESHELL bug)
- [x] 3.1 `make loop-collect` — TWO docker_run calls; BOTH ran (unit 525 + integration 202 collect), RC=0
- [x] 3.2 `make regen-doc-sync-fixtures` — regen (docker_run) THEN pytest re-test (docker_run); both ran, RC=0
- [x] 3.3 `make record-work CHANGE=harden-docker-run-oneshell` — all 3 steps ran (prompt+hermes+wiki write), 0 `git: not found`, RC=0

## 4. Verify full hermetic loop gate (regression guard)
- [x] 4.1 `make loop-ts-floor` — TS surface floor vs origin/main (RC=0, PASS)
- [x] 4.2 `make loop-unit-real` — real agent units on live Ollama (RC=0, 525 passed, ran not skipped)
- [x] 4.3 `make loop-e2e` — 3 standing e2e gates on live Ollama (RC=0, 5 passed: base64/change-driven/greetings/ticket20/ticket22)
- [x] 4.4 `make loop-integration` — fast integration subset (RC=0)
- [x] 4.5 `make loop-build-app` — tsc/rollup build (RC=0, real `created dist/main.js`, no false-green)
- [x] 4.6 `make loop-test-app` — jest (RC=0, 3 suites / 65 tests passed)

## 5. Final verification
- [x] 5.1 `openspec validate harden-docker-run-oneshell` passes
- [x] 5.2 All tasks above ticked with real `make` output captured
