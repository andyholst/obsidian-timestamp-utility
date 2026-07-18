#!/usr/bin/env python3
"""Refresh the README 'Release / Changelog' block to the current plugin version.

Idempotent: the release-notes content lives between `<!-- RELEASE_NOTES -->` markers in
README.md. If the markers exist, only the text *between* them is replaced; anything before the
first marker and after the second marker is preserved. If the markers are absent, the block is
appended to the end of the file.

The block mirrors the git_chglog categories (chglog/config.yml) so the README and CHANGELOG.md
agree on how commits are SECTIONED by Conventional-Commit type. Run by `make release-notes`
(release-automation change). No git commit/push (B14).
"""
from __future__ import annotations

import json
import sys

MARK = "<!-- RELEASE_NOTES -->"

# (emoji+label, conventional type) -- must mirror chglog/config.yml title_maps.
SECTIONS = [
    ("\U0001f680 New Features", "feat"),
    ("\U0001f41e Bug Fixes", "fix"),
    ("\u26a1 Improvements", "perf"),
    ("\U0001f527 Improvements", "refactor"),
    ("\U0001f4dd Documentation", "docs"),
    ("\U0001f6a0\ufe0f Maintenance", "chore"),
]


def build_block(version: str) -> str:
    tag = f"v{version}"
    lines = [
        MARK,
        "## Release / Changelog",
        "",
        f"Current plugin version: **{version}** (tag `{tag}`).",
        "",
        "The changelog is SECTIONED by commit type (git_chglog, `chglog/config.yml`):",
    ]
    for label, ctype in SECTIONS:
        lines.append(f"- {label} (`{ctype}`)")
    lines += [
        "",
        "The full, per-version, categorized history lives in [CHANGELOG.md](CHANGELOG.md). "
        "The squashed",
        "release commit is written with a Conventional `type(scope):` prefix so it lands in the "
        "correct",
        "section and decides the version bump (feat/fix/perf -> minor, refactor/docs/chore -> "
        "patch).",
        MARK,
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: update-release-notes.py <path-to-README.md>", file=sys.stderr)
        return 2
    readme = sys.argv[1]
    try:
        with open("package.json", encoding="utf-8") as fh:
            version = json.load(fh)["version"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"RELNOTES: cannot read version from package.json: {exc}", file=sys.stderr)
        return 1

    block = build_block(version)
    try:
        with open(readme, encoding="utf-8") as fh:
            txt = fh.read()
    except OSError as exc:
        print(f"RELNOTES: cannot read {readme}: {exc}", file=sys.stderr)
        return 1

    if MARK in txt:
        before, rest = txt.split(MARK, 1)
        after = rest.split(MARK, 1)[1] if MARK in rest else ""
        # Idempotent: strip leading blank lines so re-runs don't accumulate whitespace
        # between the closing marker and the following content.
        after = after.lstrip("\n")
        if after and not after.startswith("\n"):
            after = "\n" + after
        txt = before + block + after
    else:
        txt = txt.rstrip() + "\n\n" + block

    with open(readme, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(f"RELNOTES: README release-notes block refreshed to {version} ({readme})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
