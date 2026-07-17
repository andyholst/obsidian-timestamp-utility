#!/usr/bin/env bash
# pr_resolve.sh — B28b (PR-review stability): gh-driven PR comment resolution.
#
# Usage: scripts/pr_resolve.sh <branch>
#
# Resolves the GitHub PR for <branch> via the `gh` CLI, prints the consolidated
# list of comments + review threads, and exits. This script ONLY fetches + prints;
# it performs NO commit and NO push. The agent reads the printed threads, makes the
# code fixes, commits each as a NORMAL (non-squashed) Conventional commit, and pushes
# the PR branch normally (never --force, never squash).
#
# Exit codes:
#   0  PR found; comments/reviews printed (agent now resolves them)
#   1  no open PR for <branch>, or gh/token unavailable, or usage error
set -euo pipefail

BRANCH="${1:-}"
if [ -z "$BRANCH" ]; then
  echo "USAGE: scripts/pr_resolve.sh <branch>" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "pr-resolve: 'gh' CLI not found -- cannot fetch PR. Aborting (no commit/push)." >&2
  exit 1
fi
if [ -z "${GH_TOKEN:-}" ]; then
  echo "pr-resolve: GH_TOKEN not set -- cannot fetch PR. Aborting (no commit/push)." >&2
  exit 1
fi

# Top-level PR state (robust: gh --jq, not fragile grep over nested JSON).
STATE="$(gh pr view "$BRANCH" --json state --jq '.state' 2>/dev/null || true)"
if [ -z "$STATE" ]; then
  echo "pr-resolve: no open PR found for branch '$BRANCH'. Aborting (no commit/push)." >&2
  exit 1
fi
if [ "$STATE" != "OPEN" ]; then
  echo "pr-resolve: PR for '$BRANCH' is $STATE (not OPEN). Aborting (no commit/push)." >&2
  exit 1
fi

NUM="$(gh pr view "$BRANCH" --json number --jq '.number' 2>/dev/null)"
URL="$(gh pr view "$BRANCH" --json url --jq '.url' 2>/dev/null)"
TITLE="$(gh pr view "$BRANCH" --json title --jq '.title' 2>/dev/null)"

echo "==================================================================="
echo "PR-RESOLVE: PR #$NUM — $TITLE"
echo "URL: $URL"
echo "Branch: $BRANCH"
echo "==================================================================="
echo ""
echo "--- COMMENTS (github PR comments) ---"
gh pr view "$BRANCH" --comments 2>/dev/null || echo "(none)"
echo ""
echo "--- REVIEWS (github pr reviews) ---"
gh pr view "$BRANCH" --json reviews --jq '.reviews[]? | "\(.author.login) (\(.state)): \(.body // "")"' 2>/dev/null || echo "(none)"
echo ""
echo "--- REVIEW THREADS / pending comments (github pr review-comment list) ---"
gh api "repos/:owner/:repo/pulls/$NUM/comments" --jq '.[] | "\(.user.login) @L\(.original_line // .line) in \(.path): \(.body // "")"' 2>/dev/null || echo "(none)"
echo ""
echo "==================================================================="
echo "AGENT LOOP (B28b): for EACH item above, make the code fix, commit it as a"
echo "NORMAL (non-squashed) Conventional commit, then 'git push origin $BRANCH'"
echo "(never --force, never squash). Do NOT run squash-commits / loop-finish /"
echo "openspec-redeliver on this branch — B28a forbids squashing an engaged PR."
echo "==================================================================="
exit 0
