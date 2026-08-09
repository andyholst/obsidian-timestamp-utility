#!/usr/bin/env python3
"""gen_changelog.py — Generate the unreleased changelog section from commits since the latest tag.

Mirrors scripts/gen_changelog.sh: reads commits after the latest semver tag using git log,
groups them by Conventional-Commit type, then merges into CHANGELOG.md via merge_changelog.py.

Why this approach (and not git-chglog's full-log mode):
  git-chglog range mode (`<tag>..HEAD`) errors in this environment; full-log mode drags in
  leaking off-branch probe commits. Range-based git log is hermetic and branch-accurate.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile


# Grouped Conventional-Commit type mapping (matches commitlint semantics).
GROUP_MAP = {
    "feat": "✨ New Features",
    "fix": "🐞 Bug Fixes",
    "perf": "⚡ Performance Improvements",
    "refactor": "🔧 Refactor Improvements",
    "docs": "📝 Documentation",
    "chore": "🛠️ Maintenance",
}
DEFAULT_GROUP = "🔍 Changes"

TYPE_RE = re.compile(r"^(?P<t>feat|fix|perf|refactor|docs|chore)(?:\([^)]*\))?:\s*(?P<s>.*)$", re.I)
SKIP_RE = re.compile(r"^(Signed-off-by:|Co-Authored-by:|# )", re.I)


def ensure_repo_root() -> str:
    """Resolve project root from env, docker mount point, or this script."""
    if os.environ.get("PROJECT_ROOT"):
        return os.environ["PROJECT_ROOT"]
    # Docker compose mount point (B24 compatibility).
    candidate = "/project"
    if os.path.isdir(candidate):
        try:
            subprocess.run(
                ["git", "-C", candidate, "rev-parse", "--is-inside-work-tree"],
                check=True, capture_output=True, timeout=5,
            )
            return candidate
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    # Fall back to this script's repo parent.
    here = os.path.abspath(os.path.dirname(__file__))
    while here != "/":
        if os.path.isdir(os.path.join(here, ".git")):
            return here
        if os.path.isdir(os.path.join(here, "openspec", "changes")):
            return here
        here = os.path.dirname(here)
    return os.getcwd()


def resolve_latest_tag(repo_root: str) -> tuple[str | None, str]:
    """Return (resolved_tag_name, git_range) for commits since the latest semver tag.

    Tags may mix '0.4.10' and 'v0.4.11'; we prefer the versioned form in git where it exists.
    If no tags exist at all, we use HEAD..HEAD range.
    """
    try:
        raw = subprocess.check_output(
            ["git", "-C", repo_root, "tag", "--list"], text=True, stderr=subprocess.DEVNULL, timeout=10,
        ).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None, "HEAD"

    # Normalize: strip leading 'v', then sort by version.
    tags = sorted((t.lstrip("v") for t in raw.splitlines() if t.strip()), key=lambda x: tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-]", x)))
    if not tags:
        return None, "HEAD"

    latest_stripped = tags[-1]
    # Prefer the canonical 'v...' form if it exists.
    canonical = None
    for pref in ("v", ""):
        candidate = f"{pref}{latest_stripped}"
        try:
            subprocess.run(
                ["git", "-C", repo_root, "rev-parse", candidate],
                check=True, capture_output=True, timeout=5,
            )
            canonical = candidate
            break
        except (subprocess.SubprocessError, FileNotFoundError):
            continue

    tag = canonical or latest_stripped
    return tag, f"{tag}..HEAD"


def render_unreleased_section(repo_root: str, range_arg: str) -> str:
    """Render the unreleased changelog section from commits in the given range."""
    try:
        # Fetch commits oldest-first with hash + full message. Format: HASH\x1fMESSAGE\x1eENTRY\x1e...
        raw = subprocess.check_output(
            ["git", "-C", repo_root, "log", "--reverse", "--format=%H%x1f%B%x1e", range_arg],
            text=True, stderr=subprocess.DEVNULL, timeout=30,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return "## Unreleased\n\n(no commits in range)\n"

    groups = {t: [] for t in GROUP_MAP}
    default_items = []

    for entry in raw.split("\x1e"):
        entry = entry.strip("\n")
        if "\x1f" not in entry:
            continue
        commit_hash, msg = entry.split("\x1f", 1)
        _ = commit_hash  # unused now; kept for traceability

        msg_lines = [ln.rstrip() for ln in msg.splitlines()]

        subject = ""
        for ln in msg_lines:
            if ln.strip():
                subject = ln.strip()
                break
        if not subject:
            continue

        # Body lines from the second line onward, excluding blanks and metadata markers.
        body_lines = []
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
            items = groups[m.group("t").lower()]
        else:
            items = default_items

        items.append((subject, body_lines))

    out = ["## Unreleased", ""]

    def render_items(items):
        blk = []
        for sub, blist in items:
            blk.append(f"- **{sub}**")
            for bl in blist:
                prefix = "  - " if not bl.startswith("-") else "  "
                blk.append(prefix + bl)
            blk.append("")
        return blk

    for t, title in GROUP_MAP.items():
        if groups[t]:
            out.append(f"### {title}")
            out.append("")
            out.extend(render_items(groups[t]))

    if default_items:
        out.append(f"### {DEFAULT_GROUP}")
        out.append("")
        out.extend(render_items(default_items))

    if len(out) <= 2:
        # No commits in range: emit minimal valid header.
        return "## Unreleased\n\n\n"

    return "\n".join(out).rstrip("\n") + "\n"


def merge_changelog(new_section: str, changelog_path: str) -> None:
    """Merge new unreleased section into existing CHANGELOG.md."""
    merge_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "merge_changelog.py"
    )

    if not os.path.isfile(merge_script):
        # Inline merge logic: just prepend the new section.
        with open(changelog_path, "a", encoding="utf-8") as f:
            f.write("\n\n" + new_section)
        return

    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as tmp:
        tmp.write(new_section)
        tmp_path = tmp.name

    subprocess.run(
        [sys.executable, merge_script, tmp_path, changelog_path],
        check=True, timeout=60,
    )
    os.unlink(tmp_path)


def main() -> int:
    repo_root = ensure_repo_root()

    # Ensure git safe directory (containerized/rootless nerdctl scenario).
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", repo_root],
        capture_output=True, timeout=5, check=False,
    )

    tag, range_arg = resolve_latest_tag(repo_root)
    if tag:
        print(f"GEN-CHANGELOG: commits after latest tag '{tag}' (range '{range_arg}')")
    else:
        print(f"GEN-CHANGELOG: no tags found; rendering full branch ({range_arg})")

    new_section = render_unreleased_section(repo_root, range_arg)
    changelog_path = os.path.join(repo_root, "CHANGELOG.md")

    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as tmp:
        tmp.write(new_section)
        tmp_path = tmp.name

    try:
        merge_changelog_file = os.path.join(repo_root, "scripts", "merge_changelog.py")
        if os.path.isfile(merge_changelog_file):
            subprocess.run(
                [sys.executable, merge_changelog_file, tmp_path, changelog_path],
                check=True, timeout=60,
            )
            print("GEN-CHANGELOG: merged via merge_changelog.py")
        else:
            # Fallback: simple append.
            with open(changelog_path, "a", encoding="utf-8") as f:
                f.write(new_section)
            print("GEN-CHANGELOG: appended to CHANGELOG.md (merge_changelog.py not found)")
    finally:
        os.unlink(tmp_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
