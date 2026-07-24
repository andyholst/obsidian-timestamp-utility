#!/opt/homebrew/bin/bash
# Generate the NEW changelog `## Unreleased` section from the commits AFTER the latest tag
# (range `<latest-tag>..HEAD`) and OVERWRITE-merge it onto the existing CHANGELOG.md.
#
# Why this approach (and not git-chglog's full-log mode):
#   git-chglog 0.15.4's range mode (`<tag>..HEAD`) errors with "could not find the tag" in this
#   environment, and its full-log mode drags in EVERY reachable commit (including leaked probe
#   commits from other branches/worktrees) grouped under the nearest tag. That produced a
#   changelog misaligned with the actual branch. We instead render the unreleased range directly
#   from `git log <latest>..HEAD`, grouped by Conventional-Commit type, so the section is always
#   aligned with `git log <latest>..HEAD` and excludes off-branch/leaked commits.
set -euo pipefail

# PROJECT_ROOT: prefer explicit env, else /project (the docker compose mount point),
# else fall back to this script's directory's parent (so it also works when run directly
# from a git worktree, where /project is not mounted — B24 compatibility).
if [ -n "${PROJECT_ROOT:-}" ]; then
  :
elif [ -d /project ] && git -C /project rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  PROJECT_ROOT=/project
else
  PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "$PROJECT_ROOT"
export HOME=/tmp
export GIT_CONFIG_GLOBAL=/tmp/gitconfig
git config --global --add safe.directory "$PROJECT_ROOT" 2>/dev/null || true

CFG="$PROJECT_ROOT/chglog/config.yml"
TPL="$PROJECT_ROOT/chglog/CHANGELOG.tpl.md"
OUT="$PROJECT_ROOT/CHANGELOG.md"
TMP="$(mktemp)"

# Latest released tag by SEMVER (tags may mix `0.4.10` and `v0.4.11` prefixes).
LATEST_TAG="$(git -C "$PROJECT_ROOT" tag --list 2>/dev/null | sed -E 's/^v//' | sort -V | tail -1)"
if [ -n "$LATEST_TAG" ]; then
  if git -C "$PROJECT_ROOT" rev-parse "v$LATEST_TAG" >/dev/null 2>&1; then
    LATEST_TAG="v$LATEST_TAG"
  fi
  RANGE="$LATEST_TAG..HEAD"
else
  RANGE="HEAD"
fi
echo "GEN-CHANGELOG: commits after latest tag '$LATEST_TAG' (range '$RANGE')"

# Render the unreleased range. Prefer git-chglog if its range mode works; otherwise fall back
# to a direct git-log render grouped by Conventional-Commit type (the reliable path here).
if git-chglog --config "$CFG" --template "$TPL" "$RANGE" > "$TMP" 2>/dev/null && [ -s "$TMP" ]; then
  echo "GEN-CHANGELOG: git-chglog range render OK"
else
  echo "GEN-CHANGELOG: git-chglog range unavailable -> rendering from git log (type-grouped, body included)"
  python3 - "$RANGE" "$TMP" <<'PY'
import sys, re, subprocess
range_arg, out_path = sys.argv[1], sys.argv[2]
repo = subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip()
# commits in range, oldest-first: hash + FULL message (%B). The FIRST line is the subject
# (drives the Conventional-Commit type / section); remaining non-empty lines are the body
# and are rendered indented under the same type section.
raw = subprocess.check_output(
    ['git','log','--reverse','--format=%H%x1f%B%x1e', range_arg],
    stderr=subprocess.DEVNULL,
).decode()
GROUP_MAP = {
    'feat': '✨ New Features',
    'fix':  '🐞 Bug Fixes',
    'perf': '⚡ Performance Improvements',
    'refactor': '🔧 Refactor Improvements',
    'docs': '📝 Documentation',
    'chore': '🛠️ Maintenance',
}
DEFAULT = '🔍 Changes'
TYPE_RE = re.compile(r'^(?P<t>feat|fix|perf|refactor|docs|chore)(?:\([^)]*\))?:\s*(?P<s>.*)$', re.I)
# Lines we never surface (changelog-internal noise, signed-off-by, etc.)
SKIP_RE = re.compile(r'^(Signed-off-by:|Co-Authored-by:|# )', re.I)
groups = {g: [] for g in GROUP_MAP}
default_items = []
for entry in raw.split('\x1e'):
    entry = entry.strip('\n')
    if '\x1f' not in entry:
        continue
    h, msg = entry.split('\x1f', 1)
    msg_lines = [ln.rstrip() for ln in msg.splitlines()]
    # subject = first non-empty line
    subject = ''
    for ln in msg_lines:
        if ln.strip():
            subject = ln.strip()
            break
    if not subject:
        continue
    # body = remaining lines, excluding blank + skip lines
    body_lines = []
    seen_subject = False
    for ln in msg_lines:
        if not seen_subject:
            if ln.strip() == subject:
                seen_subject = True
            continue
        if ln.strip() == '':
            continue
        if SKIP_RE.match(ln.strip()):
            continue
        body_lines.append(ln.strip())
    m = TYPE_RE.match(subject)
    if m:
        items = groups[m.group('t').lower()]
    else:
        items = default_items
    items.append((subject, body_lines))
out = ['## Unreleased', '']
def render_items(items):
    blk = []
    for subject, body_lines in items:
        blk.append(f'- **{subject}**')
        for bl in body_lines:
            # render body line as an indented sub-bullet / wrapped description
            blk.append(f'  - {bl}' if not bl.startswith('-') else f'  {bl}')
        blk.append('')
    return blk
for t, title in GROUP_MAP.items():
    if groups[t]:
        out.append(f'### {title}')
        out.append('')
        out.extend(render_items(groups[t]))
if default_items:
    out.append(f'### {DEFAULT}')
    out.append('')
    out.extend(render_items(default_items))
if len(out) <= 2:
    # No commits in range: emit a minimal (still valid) Unreleased header.
    out = ['## Unreleased', '', '']
open(out_path,'w').write('\n'.join(out).rstrip('\n') + '\n')
PY
fi

python3 "$PROJECT_ROOT/scripts/merge_changelog.py" "$TMP" "$OUT"
rm -f "$TMP"
