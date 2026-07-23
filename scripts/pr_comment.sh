#!/opt/homebrew/bin/bash
# pr_comment.sh — B29a (PR-review stability / two-way interaction): post a comment on a PR.
#
# Usage: scripts/pr_comment.sh <branch> <body>
#
# Posts <body> as a comment on the open PR for <branch> via `gh pr comment`. Performs NO
# local commit and NO push — it only creates the GitHub comment so the participant can see
# the fix and resolve the thread. Refuses (exit non-zero) when there is no open PR or no token.
#
# Exit codes:
#   0  comment posted; prints the comment URL
#   1  usage error, no open PR for <branch>, or gh/token unavailable
set -euo pipefail

BRANCH="${1:-}"
BODY="${2:-}"
if [ -z "$BRANCH" ] || [ -z "$BODY" ]; then
  echo "USAGE: scripts/pr_comment.sh <branch> <body>" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "pr-comment: 'gh' CLI not found -- cannot post. Aborting." >&2
  exit 1
fi
if [ -z "${GH_TOKEN:-}" ]; then
  echo "pr-comment: GH_TOKEN not set -- cannot post. Aborting." >&2
  exit 1
fi

STATE="$(gh pr view "$BRANCH" --json state --jq '.state' 2>/dev/null || true)"
if [ "$STATE" != "OPEN" ]; then
  echo "pr-comment: no OPEN PR for branch '$BRANCH' (state='${STATE:-none}'). Aborting." >&2
  exit 1
fi

# Post the comment. gh pr comment reads body from -b/--body.
OUT="$(gh pr comment "$BRANCH" --body "$BODY" 2>&1)" || {
  echo "pr-comment: gh pr comment failed:" >&2
  echo "$OUT" >&2
  exit 1
}
echo "pr-comment: posted on PR for '$BRANCH':"
echo "$OUT"
exit 0
