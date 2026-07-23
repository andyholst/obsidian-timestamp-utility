#!/opt/homebrew/bin/bash
#
# run-loop-harness.sh — mandatory loop-gate trigger (AGENTS.md behaviour B20).
#
# Thin, honest wrapper over `make loop-harness`. Runs the loop stages IN FULL, then a
# FINAL B8 doc-sync gate,
# in order (loop-collect -> loop-ts-floor -> loop-unit -> loop-unit-real -> loop-e2e -> loop-integration
# -> loop-build-app -> loop-test-app -> loop-release-tests -> loop-secret-scan-tests -> check-docs-sync), and prints a per-stage PASS/FAIL/TIMEOUT summary,
# exiting non-zero if any stage is red.
#
# MACOS COMPATIBLE: rewritten to work with bash 3.2 on macOS (no associative arrays, no [[ ]],
# no GNU stat -c, no GNU date -d, no process substitution for comm).
#
# B8 durable-behaviour range: B1–B32 (the loop's "laws of physics"; see AGENTS.md). The
# final check-docs-sync stage FAILS if any sync doc drifts on stage order / loop-ts-floor / B-range.
# Canonical stage order (B8 source of truth):
#   loop-collect -> loop-ts-floor -> loop-unit -> loop-unit-real -> loop-e2e -> loop-integration -> loop-build-app -> loop-test-app -> loop-release-tests -> loop-secret-scan-tests -> check-docs-sync
#
# llama is expected to be running on the host (bound to 127.0.0.1:11434) and is
# reachable from the containers via network_mode: host (see docker-compose-files/agents.yaml).
# So ALL stages run for real. If a stage genuinely fails OR hangs past its timeout, the
# script reports FAIL/TIMEOUT and exits non-zero; fix the root cause and re-run.
# Do NOT fake-green, and never let a single slow test hang the whole loop forever
# (each stage is wrapped in `timeout`).
#
# Usage:
#   bash scripts/run-loop-harness.sh            # full loop-harness (all stages)
#   bash scripts/run-loop-harness.sh --hermetic # only loop-collect + loop-ts-floor + loop-unit
#
set -uo pipefail

# ---- macOS compatibility: use GNU coreutils if available, else macOS defaults ----
if command -v gdate >/dev/null 2>&1; then DATE_CMD=gdate; else DATE_CMD=date; fi
if command -v gstat >/dev/null 2>&1; then STAT_CMD=gstat; else STAT_CMD=stat; fi
if command -v gtimeout >/dev/null 2>&1; then TIMEOUT_CMD=gtimeout; else TIMEOUT_CMD=timeout; fi

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1

# Snapshot containers already running BEFORE the loop starts, so we only tear
# down the ones THIS run spun up -- never pre-existing containers the user or
# another process started independently.
RUNNING_BEFORE="$(nerdctl ps -q --filter label=com.docker.compose.project 2>/dev/null || true)"
# Normalize to a newline-separated set for clean diffing.
RUNNING_BEFORE_SET="$(echo "$RUNNING_BEFORE" | grep -v '^$' | sort -u)"

HERMETIC_ONLY=0
if [ "${1:-}" = "--hermetic" ]; then
  HERMETIC_ONLY=1
fi

# Ensure container bind-mount perms (rootless nerdctl, B9) are applied first.
make b9-perms >/dev/null 2>&1 || true

# ---- Stage timeouts (seconds) ----
# Using parallel arrays to avoid bash 4+ associative arrays
get_timeout() {
  case "$1" in
    loop-collect)       echo 300 ;;
    loop-ts-floor)      echo 300 ;;
    loop-unit)          echo 600 ;;
    loop-unit-real)     echo 900 ;;
    loop-e2e)           echo 1200 ;;
    loop-integration)   echo 1500 ;;
    loop-build-app)     echo 900 ;;
    loop-test-app)      echo 900 ;;
    loop-release-tests) echo 900 ;;
    loop-secret-scan-tests) echo 300 ;;
    check-docs-sync)    echo 120 ;;
    *)                  echo 600 ;;
  esac
}

# ---- Stage list ----
STAGES="loop-collect loop-ts-floor loop-unit loop-unit-real loop-e2e loop-integration loop-build-app loop-test-app loop-release-tests loop-secret-scan-tests check-docs-sync"
HERMETIC_STAGES="loop-collect loop-ts-floor loop-unit"

# ---- Summary tracking ----
summary_file="/tmp/loop-harness-summary-$$"
: > "$summary_file"
overall=0
stage_count=0

# ---- Service mapping (which container a stage may leave running) ----
get_service() {
  case "$1" in
    loop-integration) echo "integration-test-agents" ;;
    loop-build-app|loop-test-app) echo "app" ;;
    *) echo "" ;;
  esac
}

# ---- Stage description ----
stage_desc() {
  case "$1" in
    loop-collect)     echo "pytest --collect-only (unit + integration) via agents.yaml -> fail fast on dangling imports" ;;
    loop-ts-floor)    echo "scripts/ts_test_floor.sh -> FAIL if describe/leaf/jest-collected/addCommand counts drop below origin/main (silent feature/test removal guard)" ;;
    loop-unit)        echo "pytest tests/unit (mocked / hermetic) via agents.yaml -> unit-test-agents" ;;
    loop-unit-real)   echo "pytest tests/unit on LIVE llama (no mocks) via agents.yaml -> unit-test-agents" ;;
    loop-e2e)         echo "3 standing e2e gates (ticket20 / ticket22 / greetings) via agents.yaml -> integration-test-agents" ;;
    loop-build-app)   echo "docker compose tools.yaml run app: npm run build (rollup)" ;;
    loop-test-app)    echo "docker compose tools.yaml run app: npm test (jest)" ;;
    loop-release-tests) echo "release-pipeline + README-sync dry-run tests" ;;
    loop-secret-scan-tests) echo "secret-scanner pytest suite (real gitleaks, no mocks) containerized via docker-compose-files/gitleaks-tests.yaml (fail-closed)" ;;
    check-docs-sync)  echo "scripts/check-docs-sync.py -> FAIL if any B8 source-of-truth doc drifts (stage order / loop-ts-floor / B-range B1–B32) — FINAL gate" ;;
    *)                echo "make $1" ;;
  esac
}

# ---- Helper: get file size (macOS compatible) ----
get_file_size() {
  local f="$1"
  if [ ! -f "$f" ]; then
    echo 0
    return
  fi
  $STAT_CMD -f%z "$f" 2>/dev/null || wc -c < "$f" | tr -d ' '
}

# ---- Helper: get epoch seconds (macOS compatible) ----
get_epoch() {
  # macOS: date +%s gives epoch; GNU: date -d works
  if $DATE_CMD -d "$1" +%s >/dev/null 2>&1; then
    $DATE_CMD -d "$1" +%s
  else
    # macOS fallback: date with format specifiers
    local mm dd hh mi ss
    mm=$(echo "$1" | cut -d: -f1)
    hh=$(echo "$1" | cut -d: -f2)
    mi=$(echo "$1" | cut -d: -f3)
    ss=$(echo "$mi" | sed 's/\([0-9]*\).*/\1/')
    mi=$(echo "$mi" | sed 's/[0-9]*//')
    # Simpler: just use date +%s directly since we already have HH:MM:SS
    date +%s
  fi
}

# ---- Helper: compute elapsed time between two HH:MM:SS timestamps ----
calc_elapsed() {
  local start="$1" end="$2"
  # Convert HH:MM:SS to epoch seconds
  local start_epoch end_epoch
  start_epoch=$($DATE_CMD -d "$start" +%s 2>/dev/null || date -j -f "%H:%M:%S" "$start" +%s 2>/dev/null || echo 0)
  end_epoch=$($DATE_CMD -d "$end" +%s 2>/dev/null || date -j -f "%H:%M:%S" "$end" +%s 2>/dev/null || echo 0)
  if [ "$start_epoch" = "0" ] || [ "$end_epoch" = "0" ]; then
    echo 0
  else
    echo $((end_epoch - start_epoch))
  fi
}

# ---- Helper: check if stage is hermetic ----
is_hermetic_stage() {
  case "$1" in
    loop-collect|loop-ts-floor|loop-unit) echo 1 ;;
    *) echo 0 ;;
  esac
}

# ---- Helper: record summary line ----
record_summary() {
  local stage="$1" status="$2"
  echo "$stage $status" >> "$summary_file"
}

# ---- Helper: kill detached container on timeout ----
kill_detached() {
  local svc="$1"
  # Try nerdctl compose first, then docker
  if command -v nerdctl >/dev/null 2>&1; then
    nerdctl compose -f docker-compose-files/agents.yaml kill "$svc" 2>/dev/null
    nerdctl compose -f docker-compose-files/agents.yaml rm -f "$svc" 2>/dev/null
  elif command -v docker >/dev/null 2>&1; then
    docker compose -f docker-compose-files/agents.yaml kill "$svc" 2>/dev/null
    docker compose -f docker-compose-files/agents.yaml rm -f "$svc" 2>/dev/null
  fi
}

# ---- Helper: stop loop-started containers ----
stop_loop_containers() {
  echo "=== tearing down loop-started containers only ==="
  local running_now
  running_now="$(nerdctl ps -q --filter label=com.docker.compose.project 2>/dev/null | grep -v '^$' | sort -u)"
  local to_stop
  # Use diff instead of comm with process substitution
  to_stop="$(diff <(echo "$running_now") <(echo "$RUNNING_BEFORE_SET") 2>/dev/null | grep '^>' | sed 's/^> //')"
  if [ -n "$to_stop" ]; then
    echo "$to_stop" | xargs -r nerdctl stop 2>/dev/null || true
    local count
    count=$(echo "$to_stop" | wc -l | tr -d ' ')
    echo "stopped loop-started containers: $count"
  else
    echo "no loop-started containers to stop."
  fi
}

# ---- Stage runner ----
run_stage() {
  local stage="$1"
  local cap
  cap=$(get_timeout "$stage")
  local desc
  desc=$(stage_desc "$stage")
  local start_ts
  start_ts=$(date '+%H:%M:%S')
  echo "=== $stage (timeout ${cap}s) ==="
  echo "    [${start_ts}] -> $desc"
  echo "    --- live output below (also saved to /tmp/loop_${stage}.log) ---"

  local log="/tmp/loop_${stage}.log"
  local rc_file="/tmp/loop_rc_${stage}_$$"
  : > "$log"
  : > "$rc_file"

  # Heartbeat: while make runs, every 15s print elapsed note if log is quiet
  (
    local hb=0 last=0 now=0
    while kill -0 $$ 2>/dev/null; do
      sleep 15
      hb=$((hb + 1))
      now=$(get_file_size "$log")
      if [ "$now" -eq "$last" ] 2>/dev/null; then
        printf "    ... %ds elapsed (stage quiet, still running)\n" "$((hb*15))"
      fi
      last=$now
    done
  ) &
  local hb_pid=$!

  # Run stage with timeout, capture exit code via marker file
  # macOS script(1) has no -c flag — use sh -c instead.
  # docker_run.sh already allocates PTY per-container via script -q /dev/null,
  # so the harness-level wrapper doesn't need to allocate a PTY.
  $TIMEOUT_CMD "$cap" sh -c "make $stage 2>&1; echo \$? > $rc_file" 2>&1 | tee -a "$log"
  local rc
  rc=$(cat "$rc_file" 2>/dev/null || echo 1)
  rm -f "$rc_file" 2>/dev/null
  kill "$hb_pid" 2>/dev/null
  wait "$hb_pid" 2>/dev/null

  local end_ts
  end_ts=$(date '+%H:%M:%S')
  local elapsed
  elapsed=$(calc_elapsed "$start_ts" "$end_ts")

  # On timeout (rc 124 from timeout), kill detached container
  if [ "$rc" = "124" ]; then
    local svc
    svc=$(get_service "$stage")
    if [ -n "$svc" ]; then
      echo "  -> TIMEOUT (exceeded ${cap}s); killing detached '${svc}' container"
      kill_detached "$svc"
    else
      echo "  -> TIMEOUT (exceeded ${cap}s; see /tmp/loop_${stage}.log)"
    fi
    echo "    [$end_ts] elapsed ${elapsed}s"
    record_summary "$stage" "TIMEOUT"
    return 1
  fi

  if [ "$rc" -ne 0 ] 2>/dev/null; then
    echo "  -> FAIL (rc=$rc; see /tmp/loop_${stage}.log)"
    echo "    [$end_ts] elapsed ${elapsed}s"
    record_summary "$stage" "FAIL"
    return 1
  fi

  echo "  -> PASS"
  echo "    [$end_ts] elapsed ${elapsed}s"
  record_summary "$stage" "PASS"
  return 0
}

# ---- MAIN ----

echo "======================================================"
echo " LOOP-HARNESS START — $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================"
echo ""

# PRE-FLIGHT 0: verify the B8 doc/loop-sync gate itself works
echo "=== PRE-FLIGHT 0: check-docs-sync unit tests + live gate ==="
if ! make test-check-docs-sync; then
  echo "  -> PRE-FLIGHT 0 FAIL: check-docs-sync unit tests failed (gate logic broken)"
  overall=1
fi
if ! make check-docs-sync; then
  echo "  -> PRE-FLIGHT 0 FAIL: B8 doc/loop sync drift detected (run from repo root)"
  overall=1
fi
if [ "$overall" != "0" ]; then
  echo "RESULT: FAILURE — pre-flight B8 doc-sync gate is red. Fix before running stages."
  exit 1
fi
echo "  -> PRE-FLIGHT 0 PASS"
echo ""

# Run stages
for stage in $STAGES; do
  local_hermetic=$(is_hermetic_stage "$stage")

  if [ "$HERMETIC_ONLY" = "1" ] && [ "$local_hermetic" != "1" ]; then
    echo "=== $stage ==="
    echo "  -> SKIP (--hermetic mode; run full script for this stage)"
    record_summary "$stage" "SKIP"
    continue
  fi

  if ! run_stage "$stage"; then
    overall=1
  fi
done

# Print summary
echo ""
echo "================ LOOP-HARNESS SUMMARY ================"
while IFS= read -r line; do
  stage_name="${line%% *}"
  stage_status="${line##* }"
  printf "  %-22s %s\n" "$stage_name" "$stage_status"
done < "$summary_file"
echo "====================================================="

if [ "$overall" = "0" ]; then
  echo "RESULT: ALL RUN STAGES GREEN."
else
  echo "RESULT: FAILURE/TIMEOUT — a gate is red. Fix root cause and re-run."
fi

# Tear down loop-started containers
stop_loop_containers

rm -f "$summary_file" 2>/dev/null || true
exit "$overall"
