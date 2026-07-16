#!/usr/bin/env bash
#
# run-loop-harness.sh — mandatory loop-gate trigger (AGENTS.md behaviour B20).
#
# Thin, honest wrapper over `make loop-harness`. Runs the eight loop stages IN FULL, then a
# FINAL B8 doc-sync gate,
# in order (loop-collect -> loop-ts-floor -> loop-unit -> loop-unit-real -> loop-e2e -> loop-integration
# -> loop-build-app -> loop-test-app -> loop-secret-scan-tests -> check-docs-sync), and prints a per-stage PASS/FAIL/TIMEOUT summary,
# exiting non-zero if any stage is red.
#
# B8 durable-behaviour range: B1-B25 (the loop's "laws of physics"; see AGENTS.md). The
# final check-docs-sync stage FAILS if any sync doc drifts on stage order / loop-ts-floor / B-range.
# Canonical stage order (B8 source of truth):
#   loop-collect -> loop-ts-floor -> loop-unit -> loop-unit-real -> loop-e2e -> loop-integration -> loop-build-app -> loop-test-app -> loop-secret-scan-tests -> check-docs-sync
#
# Ollama is expected to be running on the host (bound to 127.0.0.1:11434) and is
# reachable from the containers via network_mode: host (see docker-compose-files/agents.yaml).
# So ALL stages run for real. If a stage genuinely fails OR hangs past its timeout, the
# script reports FAIL/TIMEOUT and exits non-zero; fix the root cause and re-run.
# Do NOT fake-green, and never let a single slow test hang the whole loop forever
# (each stage is wrapped in `timeout`).
#
# Usage:
#   bash scripts/run-loop-harness.sh            # full loop-harness (all eight stages)
#   bash scripts/run-loop-harness.sh --hermetic # only loop-collect + loop-unit (fast pre-flight)
#
set -u

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1

# Snapshot containers already running BEFORE the loop starts, so we only tear
# down the ones THIS run spun up -- never pre-existing containers the user or
# another process started independently.
RUNNING_BEFORE="$(nerdctl ps -q --filter label=com.docker.compose.project 2>/dev/null || true)"
# Normalize to a newline-separated set for clean diffing.
RUNNING_BEFORE_SET="$(echo "$RUNNING_BEFORE" | grep -v '^$' | sort -u)"

HERMETIC_ONLY=0
[[ "${1:-}" == "--hermetic" ]] && HERMETIC_ONLY=1

# Ensure container bind-mount perms (rootless nerdctl, B9) are applied first.
make b9-perms >/dev/null 2>&1 || true

# Per-stage wall-clock caps (seconds). Generous, but a hung stage must not block forever.
declare -A STAGE_TIMEOUT=(
  [loop-collect]=300
  [loop-ts-floor]=300
  [loop-unit]=600
  [loop-unit-real]=900
  [loop-e2e]=1200
  [loop-integration]=1500
  [loop-build-app]=900
  [loop-test-app]=900
  [loop-secret-scan-tests]=300
  [check-docs-sync]=120
)

STAGES=(loop-collect loop-ts-floor loop-unit loop-unit-real loop-e2e loop-integration loop-build-app loop-test-app loop-secret-scan-tests check-docs-sync)
HERMETIC=(loop-collect loop-ts-floor loop-unit)

summary=()
overall=0

# Map a loop stage to the docker-compose service whose container it may leave
# running if `make` is killed by `timeout` (compose `run` detaches the
# container, so it survives the SIGTERM to `make`). Killing it on timeout keeps
# the loop from hanging on a zombie container.
stage_service() {
  case "$1" in
    loop-integration) echo "integration-test-agents" ;;
    loop-build-app|loop-test-app) echo "app" ;;
    *) echo "" ;;
  esac
}

# Human-readable description of what each stage drives (shown in the start banner).
stage_desc() {
  case "$1" in
    loop-collect)     echo "pytest --collect-only (unit + integration) via agents.yaml -> fail fast on dangling imports" ;;
    loop-ts-floor)    echo "scripts/ts_test_floor.sh -> FAIL if describe/leaf/jest-collected/addCommand counts drop below origin/main (silent feature/test removal guard)" ;;
    loop-unit)        echo "pytest tests/unit (mocked / hermetic) via agents.yaml -> unit-test-agents" ;;
    loop-unit-real)   echo "pytest tests/unit on LIVE Ollama (no mocks) via agents.yaml -> unit-test-agents" ;;
    loop-e2e)         echo "3 standing e2e gates (ticket20 / ticket22 / greetings) via agents.yaml -> integration-test-agents" ;;
    loop-build-app)   echo "docker compose tools.yaml run app: npm run build (rollup)" ;;
    loop-test-app)   echo "docker compose tools.yaml run app: npm test (jest)" ;;
    loop-secret-scan-tests) echo "secret-scanner pytest suite (real gitleaks, no mocks) containerized via docker-compose-files/gitleaks-tests.yaml (fail-closed)" ;;
    check-docs-sync)  echo "scripts/check-docs-sync.py -> FAIL if any B8 source-of-truth doc drifts (stage order / loop-ts-floor / B-range B1-B25) — FINAL gate" ;;

    *)                echo "make $1" ;;
  esac
}

run_stage() {
  local stage="$1"
  local cap="${STAGE_TIMEOUT[$stage]:-600}"
  local desc
  desc="$(stage_desc "$stage")"
  local start_ts
  start_ts="$(date '+%H:%M:%S')"
  echo "=== $stage (timeout ${cap}s) ==="
  echo "    [${start_ts}] -> $desc"
  echo "    --- live output below (also saved to /tmp/loop_${stage}.log) ---"

  # `nerdctl compose run` HARDCODES `--interactive --tty`, so the container needs
  # a real console (a bare file/pipe fails with "provided file is not a console").
  # `script -qec "..." /dev/null` provides that PTY. We wrap it in `setsid` so it
  # detaches from the interactive shell's job control -- otherwise `script` gets
  # SIGSTOP'd (process state T) and the loop HANGS at stage 0 under a real TTY.
  # `tee` drains the PTY to the terminal (live) + log file. make's REAL exit code
  # is captured via a marker file (piping through `tee` alone would mask it = false green).
  local log="/tmp/loop_${stage}.log"
  local rc_file="/tmp/loop_rc_${stage}.$$"
  : > "$log"; : > "$rc_file"
  # Heartbeat: while make runs, every 15s print an elapsed note if the log has
  # been quiet (no new bytes) since the last tick -- so a long silent stage
  # still shows life instead of looking hung.
  {
    local hb=0 last=0 now=0
    while kill -0 "$$" 2>/dev/null && [[ -f "$log" ]]; do
      sleep 15
      hb=$((hb+1))
      now=$(stat -c%s "$log" 2>/dev/null || echo 0)
      if [[ "$now" -eq "$last" ]]; then
        printf "    ... %ds elapsed (stage quiet, still running)\n" "$((hb*15))"
      fi
      last=$now
    done
  } &
  local hb_pid=$!
  timeout "$cap" setsid script -qec "make $stage; echo \$? > $rc_file" /dev/null 2>&1 | tee -a "$log"
  local rc
  rc="$(cat "$rc_file" 2>/dev/null || echo 1)"
  rm -f "$rc_file" 2>/dev/null
  kill "$hb_pid" 2>/dev/null; wait "$hb_pid" 2>/dev/null

  local end_ts
  end_ts="$(date '+%H:%M:%S')"
  local elapsed
  elapsed=$(($(date -d "$end_ts" '+%s') - $(date -d "$start_ts" '+%s')))

  # On timeout, forcibly remove any detached container the stage may have left.
  local svc
  svc="$(stage_service "$stage")"
  if [[ "$rc" -eq 124 && -n "$svc" ]]; then
    echo "  -> TIMEOUT (exceeded ${cap}s); killing detached '${svc}' container"
    script -qec "docker compose -f docker-compose-files/agents.yaml kill '${svc}' 2>/dev/null; docker compose -f docker-compose-files/agents.yaml rm -f '${svc}' 2>/dev/null" /dev/null >/dev/null 2>&1 || true
    echo "    [$end_ts] elapsed ${elapsed}s"
    summary+=("$stage TIMEOUT")
    return 1
  fi
  if [[ "$rc" -eq 124 ]]; then
    echo "  -> TIMEOUT (exceeded ${cap}s; see /tmp/loop_${stage}.log)"
    echo "    [$end_ts] elapsed ${elapsed}s"
    summary+=("$stage TIMEOUT")
    return 1
  fi
  if [[ "$rc" -ne 0 ]]; then
    echo "  -> FAIL (rc=$rc; see /tmp/loop_${stage}.log)"
    echo "    [$end_ts] elapsed ${elapsed}s"
    summary+=("$stage FAIL")
    return 1
  fi
  echo "  -> PASS"
  echo "    [$end_ts] elapsed ${elapsed}s"
  summary+=("$stage PASS")
  return 0
}

# ---------------------------------------------------------------------------
# PRE-FLIGHT 0: verify the B8 doc/loop-sync gate itself BEHAVES (unit tests) and that
# the current tree is actually in sync (live gate). Runs FIRST so a broken gate or a
# drifted doc fails the whole loop before any heavy stage spins up.
# ---------------------------------------------------------------------------
echo "=== PRE-FLIGHT 0: check-docs-sync unit tests + live gate ==="
if ! make test-check-docs-sync; then
  echo "  -> PRE-FLIGHT 0 FAIL: check-docs-sync unit tests failed (gate logic broken)"
  overall=1
fi
if ! make check-docs-sync; then
  echo "  -> PRE-FLIGHT 0 FAIL: B8 doc/loop sync drift detected (run from repo root)"
  overall=1
fi
if [[ "${overall:-0}" != "0" ]]; then
  echo "RESULT: FAILURE — pre-flight B8 doc-sync gate is red. Fix before running stages."
  exit 1
fi
echo "  -> PRE-FLIGHT 0 PASS"

for stage in "${STAGES[@]}"; do
  is_hermetic=0
  for h in "${HERMETIC[@]}"; do [[ "$stage" == "$h" ]] && is_hermetic=1; done

  if [[ "$HERMETIC_ONLY" == "1" && "$is_hermetic" != "1" ]]; then
    echo "=== $stage ==="
    echo "  -> SKIP (--hermetic mode; run full script for this stage)"
    summary+=("$stage SKIP")
    continue
  fi

  if ! run_stage "$stage" "$is_hermetic"; then
    overall=1
  fi
done

echo ""
echo "================ LOOP-HARNESS SUMMARY ================"
for line in "${summary[@]}"; do
  printf "  %-18s %s\n" "${line%% *}" "${line##* }"
done
echo "====================================================="

if [[ "$overall" == "0" ]]; then
  echo "RESULT: ALL RUN STAGES GREEN."
else
  echo "RESULT: FAILURE/TIMEOUT — a gate is red. Fix root cause and re-run."
fi
# Tear down ONLY the containers THIS run started. We diff the containers
# running now against the snapshot taken at start (RUNNING_BEFORE_SET) and stop
# just the newly-spawned ones -- never pre-existing containers the user or
# another process started independently. On TIMEOUT the per-stage kill above
# already removed the offending container; this is the clean-pass path.
echo "=== tearing down loop-started containers only ==="
RUNNING_NOW_SET="$(nerdctl ps -q --filter label=com.docker.compose.project 2>/dev/null | grep -v '^$' | sort -u)"
TO_STOP="$(comm -23 <(echo "$RUNNING_NOW_SET") <(echo "$RUNNING_BEFORE_SET") 2>/dev/null)"
if [ -n "$TO_STOP" ]; then
  echo "$TO_STOP" | xargs -r nerdctl stop 2>/dev/null || true
  echo "stopped loop-started containers: $(echo "$TO_STOP" | wc -l)"
else
  echo "no loop-started containers to stop."
fi
exit "$overall"
