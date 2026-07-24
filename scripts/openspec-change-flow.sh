#!/opt/homebrew/bin/bash
# openspec-change-flow.sh — agent-driven OpenSpec lifecycle, CONFINED TO A WORKTREE.
#
# Contract (see openspec/changes/openspec-change-worktree-flow):
#   1. Create a dedicated local worktree wt/<name> (NEVER touch the parent working tree).
#   2. Scaffold the OpenSpec change INSIDE the worktree (B15 — via `openspec new change`).
#   3. Generate + verify INSIDE the worktree (run-agentics, loop-harness via worktree-override).
#   4. On green: archive (phase7-archive, spec only) INSIDE the worktree, then finalize IN the
#      worktree (squash-commits -> changelog -> bump-from-changelog -> changelog-format).
#      Squashing happens ONLY here, in the worktree (agent/harness behaviour).
#   5. Deliver = git push origin feat/<name> (PR). NO file copy back to the parent dir.
#   6. Independent/parallel: each run uses COMPOSE_PROJECT_NAME=otu-<name>.
#
# Usage: openspec-change-flow.sh --name <change> [--push] [--no-push] [--no-agentics] [--no-loop] [--push-remote <remote>]
#   --push         (alias; now the DEFAULT) push feat/<name> to the remote as the PR when green + finalized.
#   --no-push      opt OUT of auto-delivery: keep the work in the local wt/<name> sandbox (no feat branch, no PR).
#   --no-agentics  skip run-agentics (already generated / doc-only change).
#   --no-loop      skip the loop-harness gate.
#   --push-remote  remote name (default: origin)
#
# Environment: REPO_ROOT should be the main repo (defaults to the git repo root of $PWD).
set -euo pipefail

NAME=""
DO_PUSH=1   # B27: AUTO-DELIVER on completion is the default (push feat/<name> as PR). --no-push opts out.
NO_AGENTICS=0
NO_LOOP=0
PUSH_REMOTE="origin"

while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="${2:-}"; shift 2 ;;
    --push) DO_PUSH=1; shift ;;
    --no-push) DO_PUSH=0; shift ;;
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
BRANCH="wt/${NAME}"          # local sandbox branch during work (B27: promoted to feat/<name> on delivery)
FEAT_BRANCH="feat/${NAME}"   # the PR branch, created only at delivery time
WT="${REPO_ROOT}/worktrees/${NAME}"
OVERRIDE="-f docker-compose-files/worktree-override.yaml -p otu-${NAME}"
export REPO_ROOT WT_NAME="$NAME" WT_ROOT="$WT" BRANCH COMPOSE_PROJECT_NAME="otu-${NAME}" COMPOSE_OVERRIDE="$OVERRIDE"

echo "=== OPENSPEC-FLOW: ${NAME} ==="
echo "REPO_ROOT = $REPO_ROOT"
echo "WORKTREE  = $WT"
echo "BRANCH    = $BRANCH (local sandbox; promoted to $FEAT_BRANCH on delivery)"

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

# Make the credential file (.env with GH_TOKEN) ACCESSIBLE inside the worktree so the agent can
# push the branch + create the PR. It is provided as a SYMLINK to the parent repo's .env and is
# gitignored, so it can NEVER be committed or pushed to the GitHub project (the gitleaks gate +
# .gitignore both guard it). The worktree gets read access only; the file lives in the parent.
if [ -f "$REPO_ROOT/.env" ] && [ ! -e "$WT/.env" ]; then
  ln -s ../../.env "$WT/.env"
  echo "    (symlinked .env into worktree for token auth — gitignored, never committed)"
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
# B27: auto-deliver is the DEFAULT — promote the local sandbox to feat/<name> and push the PR.
if [ "$DO_PUSH" -eq 1 ]; then
  echo "=== 6. promote $BRANCH -> $FEAT_BRANCH and git push ${PUSH_REMOTE} ${FEAT_BRANCH} (opens/updates PR) ==="
  git -C "$WT" branch -m "$BRANCH" "$FEAT_BRANCH" 2>/dev/null || git -C "$WT" checkout -B "$FEAT_BRANCH"
  # Resolve an authenticated push URL. Prefer a token from .env (GH_TOKEN) — checked first inside
  # the worktree (symlinked, gitignored), then the repo root — so the push works even when the SSH
  # transport is unavailable (no host-key/askpass in the sandbox). The token is NEVER echoed; the
  # .env file is gitignored so it can never be committed/pushed to the GitHub project.
  PUSH_URL="$(git -C "$WT" remote get-url "$PUSH_REMOTE")"
  _tok=""
  for _envfile in "$WT/.env" "$REPO_ROOT/.env"; do
    if [ -z "$_tok" ] && [ -f "$_envfile" ]; then
      _tok="$(grep -E '^GH_TOKEN=' "$_envfile" | head -1 | cut -d= -f2-)"
    fi
  done
  if [ -n "$_tok" ]; then
    _host="$(printf '%s' "$PUSH_URL" | sed -E 's#.*@([^:/]+).*#\1#; s#.*://([^/]+).*#\1#')"
    _repo="$(printf '%s' "$PUSH_URL" | sed -E 's#.*[:/]([^/]+/[^/]+\.git).*#\1#; s#.*[:/]([^/]+/[^/]+)$#\1#')"
    PUSH_URL="https://x-access-token:${_tok}@${_host}/${_repo}"
    echo "    (using token-authenticated HTTPS push from .env)"
  fi
  git -C "$WT" push "$PUSH_URL" "$FEAT_BRANCH"
  echo "DONE: PR branch ${FEAT_BRANCH} pushed. Parent working tree was NOT modified."
else
  echo "=== 6. NOT delivering (--no-push). The squashed commit + CHANGELOG live ONLY on $BRANCH (wt/<name>) in the worktree."
  echo "      To deliver later: openspec-change-flow.sh --name $NAME  (default now auto-delivers)"
fi

echo "=== OPENSPEC-FLOW COMPLETE for ${NAME} (worktree: $WT) ==="
