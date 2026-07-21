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

echo "=== NUKE: stopping and removing ALL project containers ==="

# ── 0. PROTECT HONCHO: Get honcho container NAMES (not IDs) ──────────
# CRITICAL: nerdctl ps -q returns SHORT IDs (12 chars) while
# nerdctl compose ps -q returns FULL IDs (64 chars). ID comparison FAILS.
# SOLUTION: Use container NAMES for filtering — honcho containers always
# have names starting with "honcho-" (e.g., honcho-api-1, honcho-redis-1).
echo "Recording honcho containers for protection..."
HONCHO_NAME_LIST=""
if [ -n "$HONCHO_COMPOSE" ] && [ -f "$HONCHO_COMPOSE" ]; then
  # Get the list of honcho container names via compose ps
  COMPOSE_PS=$(timeout "$N_TIMEOUT" nerdctl compose -f "$HONCHO_COMPOSE" ps 2>/dev/null || true)
  if [ -n "$COMPOSE_PS" ]; then
    # Extract container names from compose ps output (first column of each line)
    # Format: NAME IMAGE COMMAND SERVICE STATUS PORTS
    HONCHO_NAME_LIST=$(echo "$COMPOSE_PS" | tail -n +2 | awk '{print $1}' | sort -u)
    if [ -n "$HONCHO_NAME_LIST" ]; then
      echo "Honcho containers protected (will NOT be touched):"
      echo "$HONCHO_NAME_LIST"
    else
      echo "No honcho containers running."
    fi
  else
    echo "No honcho containers running."
  fi
else
  echo "HONCHO_COMPOSE not set — no honcho containers to protect."
  echo "WARNING: honcho containers MAY be affected — set HONCHO_COMPOSE for full protection."
fi

# Helper function: check if a container name matches honcho pattern
# NOTE: Uses HONCHO_NAME_LIST populated above; NOT a heredoc to avoid
# nested-heredoc conflicts with the caller's while loop.
is_honcho_container() {
  local name="$1"
  if [ -n "$HONCHO_NAME_LIST" ]; then
    # Use grep to avoid nested heredoc issues
    if echo "$HONCHO_NAME_LIST" | grep -qx "$name"; then
      return 0  # is honcho
    fi
  fi
  # Also catch any container with name starting with "honcho-"
  if echo "$name" | grep -q '^honcho-'; then
    return 0
  fi
  return 1  # not honcho
}

# ── 1. Stop and remove project containers (excluding honcho) ─────────
# Use --format to get ID + Name pairs, then filter by name
sleep 2
echo "Listing all containers..."
ALL_CONTAINERS=$(timeout "$N_TIMEOUT" nerdctl ps -a --format '{{.ID}} {{.Names}}' 2>/dev/null || true)
if [ -n "$ALL_CONTAINERS" ]; then
  REMAINING=""
  while IFS=' ' read -r cid cname; do
    [ -z "$cid" ] && continue
    if is_honcho_container "$cname"; then
      echo "  PROTECTED (honcho): $cname"
    else
      REMAINING="$REMAINING $cid"
    fi
  done <<< "$ALL_CONTAINERS"
  REMAINING=$(echo "$REMAINING" | xargs)  # trim whitespace

  if [ -n "$REMAINING" ]; then
    echo "Stopping remaining project containers..."
    nexec stop -t 5 $REMAINING
    sleep 1
    echo "Removing project containers..."
    nexec rm -f $REMAINING
  else
    echo "No remaining containers to stop (all honcho or none)."
  fi
else
  echo "No containers to stop."
fi

# ── 2. Remove non-default networks (excluding honcho networks) ──────
echo "=== NUKE: removing project networks ==="
NETWORKS=$(timeout "$N_TIMEOUT" nerdctl network ls -q 2>/dev/null | grep -vE '^(bridge|host|none)$' || true)
if [ -n "$NETWORKS" ]; then
  # Filter out honcho networks (those starting with 'honcho_')
  PROJECT_NETS=""
  for net in $NETWORKS; do
    if echo "$net" | grep -q '^honcho_'; then
      echo "Skipping honcho network: $net"
    else
      PROJECT_NETS="$PROJECT_NETS $net"
    fi
  done
  PROJECT_NETS=$(echo "$PROJECT_NETS" | xargs)  # trim

  if [ -n "$PROJECT_NETS" ]; then
    nexec network rm $PROJECT_NETS
  else
    echo "No project networks to remove."
  fi
else
  echo "No networks to remove."
fi

# ── 3. Remove project volumes (excluding honcho volumes) ─────────────
echo "=== NUKE: removing project volumes ==="
VOLUMES=$(timeout "$N_TIMEOUT" nerdctl volume ls -q 2>/dev/null || true)
if [ -n "$VOLUMES" ]; then
  # Filter out honcho volumes (those starting with 'honcho_')
  PROJECT_VOLS=""
  for vol in $VOLUMES; do
    if echo "$vol" | grep -q '^honcho_'; then
      echo "Skipping honcho volume: $vol"
    else
      PROJECT_VOLS="$PROJECT_VOLS $vol"
    fi
  done
  PROJECT_VOLS=$(echo "$PROJECT_VOLS" | xargs)  # trim

  if [ -n "$PROJECT_VOLS" ]; then
    nexec volume rm $PROJECT_VOLS
  else
    echo "No project volumes to remove."
  fi
else
  echo "No volumes to remove."
fi

# ── 4. Remove project images (excluding honcho images) ───────────────
echo "=== NUKE: removing project images ==="
IMAGES=$(timeout "$N_TIMEOUT" nerdctl images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null || true)
if [ -n "$IMAGES" ]; then
  # Filter out honcho images (those starting with 'honcho-')
  PROJECT_IMGS=""
  for img in $IMAGES; do
    if echo "$img" | grep -q '^honcho-'; then
      echo "Skipping honcho image: $img"
    elif echo "$img" | grep -qE '^(otu-|docker-compose-files|hello-world)'; then
      PROJECT_IMGS="$PROJECT_IMGS $img"
    fi
  done
  PROJECT_IMGS=$(echo "$PROJECT_IMGS" | xargs)  # trim

  if [ -n "$PROJECT_IMGS" ]; then
    nexec rmi -f $PROJECT_IMGS
  else
    echo "No project images to remove."
  fi
else
  echo "No images to remove."
fi

echo "=== NUKE: complete ==="
