#!/usr/bin/env python3
"""pr_comment.py — B29a: post a comment on the open PR for <branch>.

Usage: python scripts/pr_comment.py <branch> <body>

Posts <body> as a comment on the open PR for <branch> via gh pr comment. No local
commit; no push — only creates the GitHub comment so the participant can see it.
Refuses when there is no open PR or no token.

Exit codes:
  0  comment posted; prints URL
  1  usage error, no open PR, or gh/token unavailable
"""

import os
import subprocess
import sys


def main():
    if len(sys.argv) < 3:
        print("USAGE: scripts/pr_comment.py <branch> <body>", file=sys.stderr)
        return 1

    branch = sys.argv[1]
    body = " ".join(sys.argv[2:])
    if not body.strip():
        print("pr-comment: body must be non-empty.", file=sys.stderr)
        return 1

    # gh presence
    if subprocess.run(["which", "gh"], capture_output=True).returncode != 0:
        print("pr-comment: 'gh' CLI not found — aborting.", file=sys.stderr)
        return 1

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print(
            "pr-comment: GH_TOKEN (or GITHUB_TOKEN) not set — aborting.",
            file=sys.stderr,
        )
        return 1

    # check PR is OPEN
    proc = subprocess.run(
        ["gh", "pr", "view", branch, "--json", "state"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        print(f"pr-comment: no PR found for branch '{branch}'.", file=sys.stderr)
        return 1

    state = proc.stdout.strip() or "{}"
    try:
        info = __import__("json").loads(state)
    except Exception:
        print("pr-comment: could not parse GH response.", file=sys.stderr)
        return 1

    if info.get("state") not in ("OPEN", "MERGED"):
        print(
            f"pr-comment: PR for '{branch}' is {info.get('state')} — not commentable. Aborting.",
            file=sys.stderr,
        )
        return 1

	# post the comment
    out = subprocess.run(
        ["gh", "pr", "comment", branch, "--body", body],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if out.returncode != 0:
        print("pr-comment: gh pr comment failed:")
        print(out.stderr.strip() or out.stdout.strip(), file=sys.stderr)
        return 1

    url = (out.stdout or "").strip().split("\n")[-1].strip()
    print(f"pr-comment: posted on PR for '{branch}': {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
