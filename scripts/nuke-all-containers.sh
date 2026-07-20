#!/usr/bin/env bash
set -uo pipefail

# ── Platform detection ───────────────────────────────────────────────
# macOS: nerdctl is a wrapper around colima nerdctl
# Linux: nerdctl is native (rootless containerd)
#
# On macOS the wrapper lives at /usr/local/bin/nerdctl and calls colima.
# On Linux nerdctl is installed directly and talks to containerd.
#
# The script uses 'nerdctl' from PATH so it works on both platforms.

N_TIMEOUT=${N_TIMEOUT:-10}
HONCHO_COMPOSE=${HONCHO_COMPOSE:-""}
PROJECT_COMPOSE_DIR=${PROJECT_COMPOSE_DIR:-"./docker-compose-files"}

# ── Timeout wrapper ──────────────────────────────────────────────────
# BSD (macOS) and GNU (Linux) both support: timeout <seconds> <cmd>
# GNU adds -k (send signal after timeout), BSD doesn't — keep it simple.
nexec() {
  timeout "$N_TIMEOUT" nerdctl "$@" 2>/dev/null || true
}

nexec_ps_q() {
  timeout "$N_TIMEOUT" nerdctl ps -q 2>/dev/null || true
}

echo "=== NUKE: stopping and removing ALL containers ==="

# ── 1. Stop honcho containers first ──────────────────────────────────
echo "Checking honcho containers..."
if [ -n "$HONCHO_COMPOSE" ] && [ -f "$HONCHO_COMPOSE" ]; then
  echo "Honcho compose file found at: $HONCHO_COMPOSE"
  HONCHO_PIDS=$(timeout "$N_TIMEOUT" nerdctl compose -f "$HONCHO_COMPOSE" ps -q 2>/dev/null || true)
  if [ -n "$HONCHO_PIDS" ]; then
    echo "Stopping honcho containers..."
    timeout "$N_TIMEOUT" nerdctl compose -f "$HONCHO_COMPOSE" down -v 2>/dev/null || true
    echo "Honcho containers stopped."
  else
    echo "No honcho containers running."
  fi
elif [ -n "$HONCHO_COMPOSE" ]; then
  echo "Honcho compose file not found at: $HONCHO_COMPOSE — skipping honcho."
else
  echo "HONCHO_COMPOSE not set — skipping honcho."
fi

# ── 2. Stop and remove remaining project containers ──────────────────
sleep 2
REMAINING=$(nexec_ps_q)
if [ -n "$REMAINING" ]; then
  echo "Stopping remaining containers..."
  nexec stop -t 5 $REMAINING
  sleep 1
  echo "Removing containers..."
  nexec rm -f $REMAINING
else
  echo "No remaining containers to stop."
fi

# ── 3. Remove non-default networks ───────────────────────────────────
echo "=== NUKE: removing ALL networks ==="
NETWORKS=$(timeout "$N_TIMEOUT" nerdctl network ls -q 2>/dev/null | grep -vE '^(bridge|host|none)$' || true)
if [ -n "$NETWORKS" ]; then
  nexec network rm $NETWORKS
else
  echo "No networks to remove."
fi

# ── 4. Remove all volumes ────────────────────────────────────────────
echo "=== NUKE: removing ALL volumes ==="
VOLUMES=$(timeout "$N_TIMEOUT" nerdctl volume ls -q 2>/dev/null || true)
if [ -n "$VOLUMES" ]; then
  nexec volume rm $VOLUMES
else
  echo "No volumes to remove."
fi

# ── 5. Remove project images ─────────────────────────────────────────
echo "=== NUKE: removing project images ==="
IMAGES=$(timeout "$N_TIMEOUT" nerdctl images 2>/dev/null | grep -E '^(honcho-|otu-|docker-compose-files|hello-world)' | awk '{print $1 ":" $2}' || true)
if [ -n "$IMAGES" ]; then
  nexec rmi -f $IMAGES
else
  echo "No project images to remove."
fi

echo "=== NUKE: complete ==="
