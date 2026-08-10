#!/usr/bin/env python3
"""pr_resolve.py — B28b: gh-driven PR comment resolution."""

import json
import os
import subprocess
import sys


def run_gh(*args):
    """Run the `gh` CLI and return stdout text. Raises RuntimeError on non-zero."""
    proc = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=60
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def main():
    if len(sys.argv) < 2:
        print("USAGE: scripts/pr_resolve.py <branch>", file=sys.stderr)
        return 1

    branch = sys.argv[1]

    # -- check gh available
    if subprocess.run(["which", "gh"], capture_output=True).returncode != 0:
        print(
            "pr-resolve: 'gh' CLI not found — cannot fetch PR. Aborting.",
            file=sys.stderr,
        )
        return 1

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print(
            "pr-resolve: GH_TOKEN (or GITHUB_TOKEN) not set — cannot fetch PR.",
            file=sys.stderr,
        )
        return 1

    # -- get PR meta
    try:
        view = run_gh("pr", "view", branch, "--json", "state,number,url,title")
        info = json.loads(view)
    except Exception as e:
        print(f"pr-resolve: no open PR found for branch '{branch}' — {e}", file=sys.stderr)
        return 1

    if info.get("state") != "OPEN":
        print(
            f"pr-resolve: PR for '{branch}' is {info.get('state') or 'MISSING'} (not OPEN). Aborting.",
            file=sys.stderr,
        )
        return 1

    num = info.get("number", "?")
    url = info.get("url", "")
    title = info.get("title", branch)

    print("=" * 80)
    print(f"PR-RESOLVE: PR #{num} — {title}")
    print(f"URL: {url}")
    print(f"Branch: {branch}")
    print("=" * 80)
    print()

    # -- comments (from gh pr view)
    try:
        run_gh("pr", "view", branch, "--comments")
    except RuntimeError as e:
        print(f"(comments failed — {e})")

    # -- reviews summary
    print("\n--- REVIEWS ---")
    try:
        reviews = run_gh(
            "pr", "view", branch, "--json", "reviews"
        )
        data = json.loads(reviews)
        for r in (data.get("reviews") or []):
            author = r.get("author", {}).get("login", "?")
            state = r.get("state", "?")
            body = (r.get("body") or "").strip()
            print(f"{author} ({state}): {body[:200]}{'...' if len(body) > 200 else ''}")
    except Exception as e:
        print(f"(reviews failed — {e})")

    # -- review threads / line comments
    print("\n--- REVIEW THREADS (line comments) ---")
    try:
        raw = run_gh("api", f"repos/:owner/:repo/pulls/{num}/comments")
        lines = json.loads(raw)
        for c in lines[:20]:  # first 20 threads only, practical limit
            user = (c.get("user") or {}).get("login", "?")
            path = c.get("path")
            line = c.get("original_line") or c.get("line")
            body = c.get("body") or ""
            print(f"{user} @L{line} in {path}: {body[:250]}{'...' if len(body) > 250 else ''}")
        if len(lines) > 20:
            print(f"(… +{len(lines) - 20} more — consider truncation if needed)")
    except Exception as e:
        print(f"(review threads failed — {e})")

    print()
    print("=" * 80)
    print("AGENT LOOP (B28b): for EACH item above, make the code fix, commit it as a")
    print(
        f"NORMAL (non-squashed) Conventional commit, then 'git push origin {branch}'"
    )
    print(
        "(never --force, never squash). Do NOT run squash-commits / loop-finish /"
    )
    print(
        "openspec-redeliver on this branch — B28a forbids squashing an engaged PR."
    )
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
