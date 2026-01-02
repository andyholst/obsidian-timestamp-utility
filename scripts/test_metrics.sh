#!/bin/bash
set -euo pipefail

action="${1:-}"
test_type="${2:-}"
log_file="${3:-}"

metrics_file="logs/test_metrics_${test_type}.txt"

mkdir -p logs

case "$action" in
  pre)
    echo "=== PRE-TEST METRICS COLLECTED for ${test_type} at $(date) ===" > "$metrics_file"
    # Docker collect-only (graceful if not running)
    if command -v docker &> /dev/null && docker compose version &> /dev/null; then
      docker compose -f docker-compose-files/agents.yaml ps >> "$metrics_file" 2>/dev/null || echo "No docker services running" >> "$metrics_file"
    else
      echo "Docker not available" >> "$metrics_file"
    fi
    cat "$metrics_file"
    ;;
  post)
    echo "=== POST-TEST METRICS EXECUTED for ${test_type} at $(date) ===" >> "$metrics_file"
    if [[ -f "$log_file" ]]; then
      # Grep for pytest summary
      passed=$(grep -i passed "$log_file" | tail -1 | grep -o '[0-9]\+' | head -1 || echo 0)
      failed=$(grep -i failed "$log_file" | tail -1 | grep -o '[0-9]\+' | head -1 || echo 0)
      skipped=$(grep -i skipped "$log_file" | tail -1 | grep -o '[0-9]\+' | head -1 || echo 0)
      echo "Tests: PASSED=${passed}, FAILED=${failed}, SKIPPED=${skipped}" >> "$metrics_file"
    else
      echo "No log file provided" >> "$metrics_file"
    fi
    cat "$metrics_file"
    ;;
  *)
    echo "Usage: $0 {pre|post} <test_type> [<log_file>]" >&2
    exit 1
    ;;
esac