#!/usr/bin/env bash
# openspec-change-flow.sh — agent-driven OpenSpec lifecycle, CONFINED TO A WORKTREE.
#
# Contract (see openspec/changes/openspec-change-worktree-flow):
#   1. Create a dedicated worktree feat/<name> (NEVER touch the parent working tree).
#   2. Scaffold the OpenSpec change INSIDE the worktree (B15 — via `openspec new change`).
#   3. Generate + verify INSIDE the worktree (run-agentics, loop-harness via worktree-override).
#   4. On green: archive (phase7-archive, spec only) INSIDE the worktree, then finalize IN the
#      worktree (squash-commits -> changelog -> bump-from-changelog -> changelog-format).
#      Squashing happens ONLY here, in the worktree (agent/harness behaviour).
#   5. Deliver = git push origin feat/<name> (PR). NO file copy back to the parent dir.
#   6. Independent/parallel: each run uses COMPOSE_PROJECT_NAME=otu-<name>.
#
# Usage: openspec-change-flow.sh --name <change> [--push] [--no-agentics] [--no-loop] [--push-remote <remote>]
#   --push         push feat/<name> to the remote as the PR when green + finalized (default: do NOT push)
#   --no-agentics  skip run-agentics (e.g. for a non-TS / doc-only change)
#   --no-loop      skip the full loop-harness (run only hermetic pre-flight gates)
#   --push-remote  remote name (default: origin)
#
# Environment: REPO_ROOT should be the main repo (defaults to the git repo root of $PWD).
set -euo pipefail

NAME=""
DO_PUSH=0
NO_AGENTICS=0
NO_LOOP=0
PUSH_REMOTE="origin"

while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="${2:-}"; shift 2 ;;
    --push) DO_PUSH=1; shift ;;
    --no-agentics) NO_AGENTICS=1; shift ;;
    --no-loop) NO_LOOP=1; shift ;;
    --push-remote) PUSH_REMOTE="${2:-origin}"; shift 2 ;;
    -h|--help) sed -n '1,30p' "$0"; exit 0 ;;
    *) echo "ERROR: unknown arg $1" >&2; exit 2 ;;
  esac
done

[ -n "$NAME" ] || { echo "ERROR: --name <change> is required" >&2; exit 2; }

# --- locate repo root (main repo) ---
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
REPO_ROOT="$(pwd)"
BRANCH="feat/${NAME}"
WT="${REPO_ROOT}/worktrees/${NAME}"
OVERRIDE="-f docker-compose-files/worktree-override.yaml -p otu-${NAME}"
export REPO_ROOT WT_NAME="$NAME" WT_ROOT="$WT" BRANCH COMPOSE_PROJECT_NAME="otu-${NAME}" COMPOSE_OVERRIDE="$OVERRIDE"

echo "=== OPENSPEC-FLOW: ${NAME} ==="
echo "REPO_ROOT = $REPO_ROOT"
echo "WORKTREE  = $WT"
echo "BRANCH    = $BRANCH"

# --- 1. create worktree (idempotent) ---
if [ -d "$WT" ]; then
  echo "WORKTREE already exists at $WT — reusing."
else
  echo "=== 1. git worktree add $WT -b $BRANCH ==="
  git worktree add "$WT" -b "$BRANCH"
fi
# node_modules is gitignored and absent from the worktree; bind the main repo's via symlink so
# the host-side tooling (openspec CLI, npm build outside containers) works. Containers already bind
# node_modules absolutely from REPO_ROOT, so this is purely for host-side convenience.
if [ ! -e "$WT/node_modules" ] && [ -d "$REPO_ROOT/node_modules" ]; then
  ln -s ../../node_modules "$WT/node_modules"
fi

# All subsequent work happens INSIDE the worktree.
cd "$WT"

# --- 2. scaffold change INSIDE the worktree (B15) ---
if [ ! -d "openspec/changes/${NAME}" ]; then
  echo "=== 2. make openspec-new NAME=${NAME} (inside worktree) ==="
  make openspec-new NAME="$NAME"
else
  echo "Change dir openspec/changes/${NAME} already present in worktree — skipping scaffold."
fi

# --- 3a. generate (optional) ---
if [ "$NO_AGENTICS" -eq 0 ]; then
  echo "=== 3a. make run-agentics CHANGE=${NAME} (inside worktree) ==="
  make run-agentics CHANGE="$NAME"
else
  echo "=== 3a. SKIPPED run-agentics (--no-agentics) ==="
fi

# --- 3b. loop gate (the decision point, B20) ---
# run-agentics / loop-harness read COMPOSE_OVERRIDE from the env -> container /project = worktree.
if [ "$NO_LOOP" -eq 0 ]; then
  echo "=== 3b. make loop-harness (inside worktree) ==="
  make loop-harness
else
  echo "=== 3b. running HERMETIC pre-flight only (--no-loop) ==="
  make loop-collect
  make loop-ts-floor
  make loop-unit
fi

echo "LOOP GATE GREEN — continuing to archive + finalize."

# --- 4. archive on green (spec only, no git commit/push) ---
echo "=== 4. make phase7-archive CHANGE=${NAME} (inside worktree) ==="
make phase7-archive CHANGE="$NAME"

# --- 5. finalize INSIDE the worktree (squash confined to worktree) ---
echo "=== 5. finalize in worktree: squash -> changelog -> bump -> format ==="
make squash-commits
make changelog
make bump-from-changelog
make changelog-format

# --- 6. deliver as PR push (NO file copy to parent) ---
if [ "$DO_PUSH" -eq 1 ]; then
  echo "=== 6. git push ${PUSH_REMOTE} ${BRANCH} (opens/updates PR) ==="
  git push "$PUSH_REMOTE" "$BRANCH"
  echo "DONE: PR branch ${BRANCH} pushed. Parent working tree was NOT modified."
else
  echo "=== 6. NOT pushing (no --push). The squashed commit + CHANGELOG live ONLY on $BRANCH in the worktree."
  echo "      To deliver: openspec-change-flow.sh --name $NAME --push"
fi

echo "=== OPENSPEC-FLOW COMPLETE for ${NAME} (worktree: $WT) ==="
