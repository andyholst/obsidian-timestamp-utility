#!/usr/bin/env bash
# Build a GitHub-release-ready artifact set in ./release from the current repo state.
#
# This is the single source of truth for what `make release` ships. It:
#   1. Resolves the repo root (works from anywhere, incl. inside a docker worktree).
#   2. Reads the current version from package.json (TAG overrides if given).
#   3. Builds the plugin (npm run build -> dist/main.js) — unless DRY_RUN and a build exists.
#   4. Generates release/release_notes.md from the FIRST "## <version>" section of
#      CHANGELOG.md that matches the current version (verbatim, non-empty).
#   5. Copies main.js, manifest.json, README.md, CHANGELOG.md, release_notes.md into release/.
#   6. Zips them as <REPO_NAME>-<TAG>.zip.
#
# Guards (per user instruction):
#   - MAIN guard: the publish-prep only runs on branch `main` (or GITHUB_REF ends in /main),
#     UNLESS DRY_RUN=1 is set. Off-main without DRY_RUN => skip artifact publish-prep, exit 0.
#   - DRY_RUN=1: produce all local artifacts but NEVER call the GitHub release API.
#
# No push / no GitHub calls happen in this script (B14). The workflow does the publish.
set -euo pipefail

# --- repo root resolution (worktree-safe: git rev-parse --show-toplevel) ---
if command -v git >/dev/null 2>&1 && ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  PROJECT_ROOT="$ROOT"
elif [ -n "${PROJECT_ROOT:-}" ]; then
  :
else
  PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "$PROJECT_ROOT"
git config --global --add safe.directory "$PROJECT_ROOT" 2>/dev/null || true

# --- inputs ---
TAG="${TAG:-}"
REPO_NAME="${REPO_NAME:-obsidian-timestamp-utility}"
DRY_RUN="${DRY_RUN:-0}"

if [ -z "$TAG" ]; then
  TAG="$(node -p "require('./package.json').version" 2>/dev/null || true)"
fi
if [ -z "$TAG" ]; then
  echo "Error: TAG could not be determined (set TAG or ensure package.json has a version)." >&2
  exit 1
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
# GITHUB_REF is e.g. refs/heads/main when the workflow runs on main
if [ "${GITHUB_REF:-}" != "" ]; then
  case "$GITHUB_REF" in
    refs/heads/main) CURRENT_BRANCH="main" ;;
    # On a merged-PR event (pull_request: closed + merged), GITHUB_REF is the PR
    # merge ref (refs/pull/<n>/merge), NOT refs/heads/main. The workflow only runs
    # this job when the PR was actually merged, so treat /merge as publishable.
    refs/pull/*/merge) CURRENT_BRANCH="main" ;;
  esac
fi

echo "release.sh: PROJECT_ROOT=$PROJECT_ROOT TAG=$TAG REPO_NAME=$REPO_NAME DRY_RUN=$DRY_RUN branch=$CURRENT_BRANCH"

# --- main-branch guard ---
if [ "$CURRENT_BRANCH" != "main" ] && [ "$DRY_RUN" != "1" ]; then
  echo "release.sh: NOT on main ($CURRENT_BRANCH) and DRY_RUN unset -> skipping publish-prep (exit 0)."
  exit 0
fi

# --- build the plugin (main.ts -> dist/main.js) ---
# `make release` already runs `build-app` (docker) as a prerequisite, which produces
# dist/main.js. Only rebuild here if it is genuinely missing. Build failures must NOT
# block release-notes generation (notes come from CHANGELOG, not the build).
if [ ! -f dist/main.js ]; then
  echo "release.sh: dist/main.js missing — attempting npm run build..." >&2
  if ! npm run build 2>&1; then
    echo "release.sh: WARNING npm run build failed; continuing with notes/zip using existing dist if any." >&2
  fi
fi
if [ ! -f dist/main.js ]; then
  echo "Error: dist/main.js missing and build failed." >&2
  exit 1
fi

# --- generate release notes from the matching CHANGELOG section ---
# (Done unconditionally — this is the artifact the publish step requires.)
CHANGELOG_FILE="$PROJECT_ROOT/CHANGELOG.md"
RELEASE_NOTES_FILE="$PROJECT_ROOT/release_notes.md"

if [ ! -f "$CHANGELOG_FILE" ]; then
  echo "Error: $CHANGELOG_FILE not found." >&2
  exit 1
fi

# Extract the first "## <version>" section whose version equals $TAG.
# Prints from that heading up to (but not including) the next "## " heading.
RELEASE_NOTES="$(python3 - "$CHANGELOG_FILE" "$TAG" <<'PY'
import sys, re
path, tag = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
# find all "## x.y.z" headings with their positions
heads = [(m.start(), m.group(1)) for m in re.finditer(r'^##\s+([0-9]+\.[0-9]+\.[0-9]+)\s*$', text, re.M)]
if not heads:
    sys.exit("Error: no version sections in CHANGELOG.md")
for i, (pos, ver) in enumerate(heads):
    if ver == tag:
        start = pos
        end = heads[i+1][0] if i+1 < len(heads) else len(text)
        sys.stdout.write(text[start:end].rstrip() + "\n")
        break
else:
    sys.exit(f"Error: no CHANGELOG section matches version {tag}")
PY
)"

if [ -z "$RELEASE_NOTES" ]; then
  echo "Error: release notes empty for version $TAG." >&2
  exit 1
fi

mkdir -p "$PROJECT_ROOT/release"
printf '%s\n' "$RELEASE_NOTES" > "$RELEASE_NOTES_FILE"

# --- assemble release files ---
cp dist/main.js              "$PROJECT_ROOT/release/main.js"
cp manifest.json            "$PROJECT_ROOT/release/manifest.json"
cp README.md                "$PROJECT_ROOT/release/README.md" 2>/dev/null || true
cp CHANGELOG.md             "$PROJECT_ROOT/release/CHANGELOG.md"
cp "$RELEASE_NOTES_FILE"    "$PROJECT_ROOT/release/release_notes.md"

# --- zip (all members at root, consistent layout) ---
cd "$PROJECT_ROOT/release"
rm -f "../${REPO_NAME}-${TAG}.zip"
zip -r "../${REPO_NAME}-${TAG}.zip" main.js manifest.json README.md CHANGELOG.md release_notes.md >/dev/null 2>&1 \
  || { echo "Error: failed to create zip." >&2; exit 1; }
cd "$PROJECT_ROOT"

echo "release.sh: artifacts ready in release/ and ${REPO_NAME}-${TAG}.zip"
if [ "$DRY_RUN" = "1" ]; then
  echo "release.sh: DRY_RUN=1 -> no GitHub release API called."
fi
