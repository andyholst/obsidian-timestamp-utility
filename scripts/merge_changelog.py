#!/usr/bin/env python3
"""Merge a freshly generated git-chglog output onto the existing CHANGELOG.md.

Correctness rules (the naive `--output` mode violates all of these):
1. Tag-name prefix drift: git tags may be `0.4.10` OR `v0.4.10`, so git-chglog emits
   `## v0.4.10` while the curated file uses `## 0.4.10`. We normalise both for comparison
   and strip the leading `v` in output so we never re-prepend already-present history.
2. Untagged HEAD: git-chglog names the top section `<last-tag> Latest` (e.g. `0.4.10 Latest`),
   which collides with the curated `## 0.4.10`. We rename that top section to `## Unreleased`.
3. git-chglog 0.15.4 ignores `commit_parsers`/`commit_groups` and dumps every commit under a
   single `### 🔍 Changes` block. We REGROUP the commit bullets by their Conventional-Commit
   type prefix (feat/fix/docs/chore/refactor/perf) into the canonical `### <emoji> <Group>`
   subsections -- identical to the curated `## 0.4.9` structure -- so the commit's type tag
   drives the section it lands in.
4. We keep ONLY the working section whose normalised key is NOT in the COMMITTED (git HEAD)
   history, and OVERWRITE (drop + re-create) it at the top. Released/curated sections are never
   touched. Idempotent: re-running `make changelog` keeps the `## ` heading count constant and
   produces no duplicate version/Unreleased headings.
"""
import sys
import os
import re
import subprocess

GROUP_MAP = {
    'feat': '✨ New Features',
    'fix': '🐞 Bug Fixes',
    'perf': '⚡ Performance Improvements',
    'refactor': '🔧 Refactor Improvements',
    'docs': '📝 Documentation',
    'chore': '🛠️ Maintenance',
}
DEFAULT_GROUP = '🔍 Changes'

TYPE_RE = re.compile(r'(?P<type>feat|fix|perf|refactor|docs|chore)(?:\([^)]*\))?:\s*', re.IGNORECASE)


def norm_heading(text):
    t = text.strip()
    t = re.sub(r'^v', '', t)
    t = re.sub(r'\s*Latest$', '', t)
    return t.strip()


def split_sections(text):
    parts = re.split(r'(?m)^(## .*)$', text)
    preamble = parts[0]
    sections = []
    i = 1
    while i < len(parts):
        heading = parts[i].replace('## ', '', 1).strip()
        body = parts[i + 1] if i + 1 < len(parts) else ''
        sections.append((heading, body))
        i += 2
    return preamble, sections


def regroup_body(body):
    """Normalise a section body: collapse duplicate consecutive group headers and stray
    blank lines. The generation step (gen_changelog.sh) already groups by Conventional-Commit
    type, so this only de-dups headers and tightens spacing (Prettier-friendly)."""
    lines = body.split('\n')
    out = []
    prev_header = None
    for ln in lines:
        s = ln.rstrip()
        if re.match(r'^###\s', s):
            if s == prev_header:
                continue  # collapse duplicate consecutive group header
            prev_header = s
        else:
            prev_header = None
        out.append(s)
    # collapse 3+ blank lines to a single blank line
    collapsed = []
    blank = 0
    for ln in out:
        if ln == '':
            blank += 1
            if blank <= 1:
                collapsed.append(ln)
        else:
            blank = 0
            collapsed.append(ln)
    return '\n'.join(collapsed).strip('\n') + '\n'


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: merge_changelog.py <generated.md> <base.md>")
    gen_path, base_path = sys.argv[1], sys.argv[2]
    gen = open(gen_path, encoding='utf-8').read()
    base = open(base_path, encoding='utf-8').read()

    # RELEASED = (a) version sections already present in the COMMITTED changelog, AND
    # (b) any version that has a git TAG (tag = released, even if the curated changelog
    # hasn't been regenerated for it yet). This prevents git-chglog's full render from
    # re-adding already-shipped versions (e.g. 0.4.10/0.4.11) as phantom "new" sections
    # when the curated CHANGELOG.md lags behind the tags.
    repo = os.path.abspath(os.path.dirname(base_path))
    try:
        committed_raw = subprocess.check_output(
            ['git', '-C', repo, 'show', 'HEAD:CHANGELOG.md'], stderr=subprocess.DEVNULL,
        ).decode()
    except Exception:
        committed_raw = base  # not committed yet -> treat whole working file as replaceable
    released = {norm_heading(m.group(1)) for m in re.finditer(r'(?m)^## (.*)$', committed_raw)}
    released.discard('Unreleased')  # working section, not a released version
    try:
        tags_raw = subprocess.check_output(
            ['git', '-C', repo, 'tag', '--list'], stderr=subprocess.DEVNULL,
        ).decode()
        for t in tags_raw.splitlines():
            released.add(norm_heading(t))  # 'v0.4.11' -> '0.4.11'
    except Exception:
        pass

    # Split the WORKING file into preamble + sections.
    preamble, base_sections = split_sections(base)
    # Keep only RELEASED sections from the working file (drop old working section -> overwrite).
    kept = [(h, b) for (h, b) in base_sections if norm_heading(h) in released]

    # Build the NEW working section(s) from the generated full render, skipping released keys.
    _, gen_sections = split_sections(gen)
    new_sections = []
    seen = set()
    for (h, b) in gen_sections:
        key = norm_heading(h)
        # A section git-chglog names "<tag> Latest" is the UNRELEASED working section
        # (commits after the latest tag) -- it MUST always become "## Unreleased" and be
        # added, even if <tag> itself is a known/released version. Check this BEFORE the
        # released-skip below, or a tag-fix would wrongly drop the user's unreleased work.
        new_h = re.sub(r'^v', '', h)
        if new_h.rstrip().endswith('Latest'):
            new_h = 'Unreleased'
            key = 'Unreleased'
        if key in released or key in seen:
            continue  # released history or duplicate within generated -> skip (dedup)
        seen.add(key)
        new_sections.append((new_h, regroup_body(b)))

    if not new_sections:
        print("merge_changelog: no new working section to add (idempotent / already present).")
        return

    new_block = "\n\n".join(f"## {h}\n{b.rstrip()}" for (h, b) in new_sections)
    parts = [preamble.rstrip(), new_block]
    if kept:
        parts.append("\n\n".join(f"## {h}\n{b.rstrip()}" for (h, b) in kept))
    out = "\n\n".join(p for p in parts if p) + "\n"
    open(base_path, 'w', encoding='utf-8').write(out)
    labels = ", ".join(h for (h, _) in new_sections)
    print("merge_changelog: wrote {0} working section(s): {1} (overwrite, idempotent)".format(len(new_sections), labels))


if __name__ == '__main__':
    main()
