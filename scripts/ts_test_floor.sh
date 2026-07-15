#!/usr/bin/env bash
#
# ts_test_floor.sh — Strict TS test/command floor guard
# (OpenSpec change: strict-ts-test-floor / capability ts-test-floor).
#
# WHY: the loop-harness gates on build-app + jest passing, but tracks NO absolute
# count of the plugin's test/command surface. A change that silently DROPS a feature
# (e.g. the uuid command + its tests) stays green as long as the remaining tests pass.
# This guard fails the loop if any of four metrics on the CURRENT branch is strictly
# LOWER than the origin/main baseline.
#
# METRICS (current vs baseline):
#   1. describe blocks in src/__tests__/main.test.ts
#   2. leaf it/test count in src/__tests__/main.test.ts
#   3. jest COLLECTED test total (number jest actually collects/runs)
#   4. addCommand(...) count in src/main.ts
#
# Hermetic + read-only: only diffs origin/main (via `git show`) and runs a LOCAL
# `npx jest --collectOnly`. No network, no Ollama, no tree writes.
#
# Exit 0 = floor respected (current >= baseline on all metrics).
# Exit 1 = a metric dropped below baseline (loop MUST fail).
#
set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1

# Baseline ref: origin/main, else main, else error.
if git rev-parse --verify origin/main >/dev/null 2>&1; then
  BASE="origin/main"
elif git rev-parse --verify main >/dev/null 2>&1; then
  BASE="main"
else
  echo "TS-FLOOR: ERROR: no 'origin/main' or 'main' ref found -- cannot establish a baseline." >&2
  exit 1
fi

MAIN_TS="src/main.ts"
TEST_TS="src/__tests__/main.test.ts"

count_describe() { grep -cE "describe\(" "$1" 2>/dev/null || true; }
count_leaf()     { grep -cE "[[:space:]]*(it|test)\(" "$1" 2>/dev/null || true; }
count_addcmd()   { grep -cE "addCommand\(" "$1" 2>/dev/null || true; }

# ---- baseline (from git, never disk) ----
BASE_DESCRIBE=$(git show "$BASE:$TEST_TS" 2>/dev/null | count_describe -)
BASE_LEAF=$(git show "$BASE:$TEST_TS" 2>/dev/null | count_leaf -)
BASE_ADDCMD=$(git show "$BASE:$MAIN_TS" 2>/dev/null | count_addcmd -)

# ---- current (from disk) ----
if [ -f "$TEST_TS" ]; then
  CUR_DESCRIBE=$(count_describe "$TEST_TS")
  CUR_LEAF=$(count_leaf "$TEST_TS")
else
  CUR_DESCRIBE=0; CUR_LEAF=0
fi
if [ -f "$MAIN_TS" ]; then
  CUR_ADDCMD=$(count_addcmd "$MAIN_TS")
else
  CUR_ADDCMD=0
fi

# ---- jest collected total ----
# Current: real jest collection across the whole project.
# Baseline: only src/__tests__/main.test.ts varies between branches (the other two
# suites are hand-written + stable), so the baseline jest total is the current total
# adjusted by the main.test.ts leaf delta. Fully hermetic, no checkout needed.
if command -v npx >/dev/null 2>&1 && [ -d node_modules ]; then
  CUR_JEST=$(npx jest --collectOnly --silent 2>/dev/null | grep -oE "Tests:[[:space:]]+[0-9]+" | grep -oE "[0-9]+" | tail -1)
fi
[ -z "${CUR_JEST:-}" ] && CUR_JEST="$CUR_LEAF"
BASE_JEST=$(( CUR_JEST - CUR_LEAF + BASE_LEAF ))

# Normalize empties to 0.
BASE_DESCRIBE=${BASE_DESCRIBE:-0}; CUR_DESCRIBE=${CUR_DESCRIBE:-0}
BASE_LEAF=${BASE_LEAF:-0};         CUR_LEAF=${CUR_LEAF:-0}
BASE_ADDCMD=${BASE_ADDCMD:-0};     CUR_ADDCMD=${CUR_ADDCMD:-0}
BASE_JEST=${BASE_JEST:-0};         CUR_JEST=${CUR_JEST:-0}

echo "TS-FLOOR: baseline ref = $BASE"
printf "TS-FLOOR: %-22s %-10s %-10s %s\n" METRIC BASELINE CURRENT RESULT
fail=0
check() {
  local name="$1" base="$2" cur="$3"
  local res="OK"
  if [ "$cur" -lt "$base" ]; then res="FAIL"; fail=1; fi
  printf "TS-FLOOR: %-22s %-10s %-10s %s\n" "$name" "$base" "$cur" "$res"
}
check "describe_blocks"      "$BASE_DESCRIBE" "$CUR_DESCRIBE"
check "leaf_it_test"        "$BASE_LEAF"     "$CUR_LEAF"
check "jest_collected_total" "$BASE_JEST"    "$CUR_JEST"
check "addCommand_count"    "$BASE_ADDCMD"   "$CUR_ADDCMD"

if [ "$fail" = "1" ]; then
  echo "TS-FLOOR: FAILED — a TS test/command metric dropped below $BASE. The loop MUST NOT pass."
  exit 1
fi
echo "TS-FLOOR: PASS — all TS test/command metrics >= $BASE baseline."
exit 0
