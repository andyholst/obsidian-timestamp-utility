#!/usr/bin/env python3
"""changelog_closed.py — Closed-loop changelog with commitlint validation (mirrors changelog.sh).

Generates a new CHANGELOG.md section for TAG by:
  1. Finding the latest tag before $TAG; commits range = <latest-tag-commit>..HEAD or just HEAD.
  2. Optionally validating commits via commitlint if it is on PATH.
  3. Grouping parsed Commit messages into ✨/🐞/⚡/🔧/📝/🛠️ sections (Conventional-Commit types).
  4. Prepending the new $TAG section after the file's header and before older versioned sections.

Writes to /app/CHANGELOG.md if /app exists (container); otherwise ./CHANGELOG.md in the repo root.

Env var: TAG=<semver> REPO_NAME=<repo-name> python3 scripts/changelog_closed.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

GROUP_MAP = {
    "feat": "✨ New Features",
    "fix": "🐞 Bug Fixes",
    "perf": "⚡ Performance Improvements",
    "refactor": "🔧 Refactor Improvements",
    "docs": "📝 Documentation",
    "chore": "🛠️ Maintenance",
}
DEFAULT_GROUP = "🔍 Changes"

TYPE_RE = re.compile(r"^(?P<t>feat|fix|perf|refactor|docs|chore)(?:\([^)]*\))?:\s*(?P<s>.*)$", re.IGNORECASE)
SKIP_RE = re.compile(r"^(Signed-off-by:|Co-Authored-by:|# )", re.IGNORECASE)


def main() -> int:
    tag = os.environ.get("TAG", "").strip()

    # Ensure git safe directory (containerized/rootless scenario).
    try:
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/app"], check=False, timeout=5, capture_output=True)
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", os.getcwd()], check=False, timeout=5, capture_output=True)
    except Exception:
        pass

    # Validate TAG.
    if not tag:
        print("Error: TAG environment variable is not set.", file=sys.stderr)
        return 1

    # Latest tag before $TAG (by creation date, excluding the current tag).
    all_tags_out = subprocess.check_output(
        ["git", "tag", "--sort=-creatordate"], text=True, stderr=subprocess.DEVNULL, timeout=30,
    ).strip()
    latest = None
    for t in all_tags_out.splitlines():
        if t.strip() != tag:
            latest = t.strip()
            break

    commit_range = "HEAD"
    latest_tag_commit = None

    if latest:
        print(f"Latest previous tag: {latest}")
        try:
            latest_tag_commit = subprocess.check_output(
                ["git", "rev-list", "-n", "1", latest], text=True, timeout=10, stderr=subprocess.DEVNULL,
            ).strip()
            commit_range = f"{latest_tag_commit}..HEAD"
        except Exception:
            pass
    else:
        print("No previous tags found; processing all commits up to HEAD.")

    # Validate with commitlint if available.
    print(f"Validating commits with commitlint from range {commit_range}...")
    has_commitlint = subprocess.run(["which", "commitlint"], capture_output=True).returncode == 0
    commits_found = False

    commit_hashes = [c.strip() for c in subprocess.check_output(
        ["git", "rev-list", "--no-merges", commit_range], text=True, stderr=subprocess.DEVNULL, timeout=120,
    ).strip().splitlines()]

    for ch in commit_hashes:
        full_msg = (subprocess.check_output(["git", "log", "-s", "--format=%B", ch], text=True, stderr=subprocess.DEVNULL)).strip()

        commits_found = True

        if has_commitlint:
            try:
                p = subprocess.Popen(
                    ["commitlint"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, timeout=30,)
                _, _err = p.communicate(input=full_msg + "\n")
                if p.returncode != 0:
                    print(f"Error: Commit {ch} does not conform to conventional commit standards.", file=sys.stderr)
                    print(full_msg, file=sys.stderr)
                    return 1
            except Exception:
                pass

    if commits_found:
        print("Commits validated successfully.")
    else:
        print(f"No new commits found since {latest or 'nothing'}")

    # Parse and group commits.
    raw = subprocess.check_output(
        ["git", "-C", os.getcwd(), "log", "--reverse", "--format=%H%x1f%B%x1e", commit_range],
        text=True, stderr=subprocess.DEVNULL, timeout=30,)

    groups: dict[str, list[tuple[str, list[str]]]] = {k: [] for k in GROUP_MAP}
    default_items: list[tuple[str, list[str]]] = []

    for entry in raw.split("\x1e"):
        entry = entry.strip("\n")
        if "\x1f" not in entry:
            continue
        parts = entry.split("\x1f", 1)
        if len(parts) != 2:
            continue

        commit_hash, msg = parts[0], parts[1]

        # Skip the commit that created the latest tag (no double-counting).
        if latest_tag_commit and commit_hash == latest_tag_commit:
            continue

        msg_lines = [ln.rstrip() for ln in msg.splitlines()]
        subject = ""
        for ln in msg_lines:
            if ln.strip():
                subject = ln.strip()
                break
        if not subject:
            continue

        body_lines: list[str] = []
        seen_subject = False
        for ln in msg_lines:
            if not seen_subject:
                if ln.strip() == subject:
                    seen_subject = True
                continue
            if not ln.strip():
                continue
            if SKIP_RE.match(ln.strip()):
                continue
            body_lines.append(ln.strip())

        m = TYPE_RE.match(subject)
        if m:
            groups[m.group("t").lower()].append((subject, body_lines))
        else:
            default_items.append((subject, body_lines))

    # Build the new changelog section for TAG.
    out_lines: list[str] = []

    def render_group(items, out):
        for title, b_list in items:
            out.append(f"- **{title}**")
            for bl in b_list:
                if not bl.startswith("-"):
                    out.append("  - " + bl)
                else:
                    out.append("  " + bl)
            out.append("")

    out_lines.append("")
    out_lines.append("## {} ".format(tag))
    out_lines.append("")

    first_section = True

    for t_key, label in GROUP_MAP.items():
        if not groups[t_key]:
            continue
        if not first_section:
            out_lines.append("")
        out_lines.append("### {} ".format(label))
        out_lines.append("")
        render_group(groups[t_key], out_lines)
        first_section = False

    if default_items:
        if not first_section:
            out_lines.append("")
        out_lines.append(f"### {DEFAULT_GROUP}")
        out_lines.append("")
        render_group(default_items, out_lines)
    elif first_section:
        # No commits matched any group.
        out_lines.append("### 🔍 No Changes")
        out_lines.append("")
        out_lines.append("- No notable changes in this release.")
        out_lines.append("")

    new_section = "\n".join(out_lines).rstrip("\n") + "\n"

    # Determine target changelog path.
    target_path = "/app/CHANGELOG.md" if os.path.isdir("/app") else ("CHANGELOG.md")

    # Merge onto existing file (header stays, new section goes first; old versions preserved below).
    header_part = ""
    old_sections = ""
    if os.path.isfile(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            existing = f.read()

        # Header is everything before the first "## " version line.
        hm = re.match(r"^(.+?)\n\n## ", existing, re.DOTALL)
        if hm:
            header_part = hm.group(1).rstrip("\n") + "\n"

        # Preserve anything after the new section insertion point (i.e., prior versioned entries).
        # We keep them verbatim so history is intact.
        remaining = re.split(r"^## .+$", existing, flags=re.MULTILINE)[::-1]
        old_sections_text = "\n".join(remaining) if len(remaining) > 1 else ""

    full_output = header_part + new_section.strip() + "\n"
    if old_sections:
        full_output += "\n" + old_sections.strip() + "\n"

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(full_output)

    print(f"Amended {target_path} with commits from {commit_range} inserted after header.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
