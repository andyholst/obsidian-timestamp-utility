#!/usr/bin/env python3
"""release.py — Build a GitHub-release-ready artifact set in ./release.

Mirrors scripts/release.sh: resolves the repo root, reads version from package.json (or TAG env),
builds the plugin via rollup/npx/npm, generates release_notes.md from CHANGELOG.md's matching
version section, then assembles release/ and zips it as <REPO_NAME>-<TAG>.zip.

Guards:
  - MAIN guard: runs only on branch main (or DRY_RUN=1). Other branches skip artifact prep, exit 0.
  - DRY_RUN=1: produce all local artifacts but NEVER call the GitHub release API.
No push / no GitHub calls (B14). The workflow does the publish.

Env vars:
  TAG          — override the version read from package.json.
  REPO_NAME    — defaults to obsidian-timestamp-utility.
  DRY_RUN      — '1' means dry run (always produce artifacts regardless of branch).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile


def ensure_repo_root() -> str:
    """Resolve project root: git rev-parse, env PROJECT_ROOT, or script's parent."""
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
            .decode("utf-8")
            .strip()
        )
    except Exception:
        pass

    if os.environ.get("PROJECT_ROOT"):
        return os.environ["PROJECT_ROOT"]

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_version(repo_root: str) -> str:
    """Return version from TAG env or package.json."""
    tag = os.environ.get("TAG", "").strip()
    if tag:
        return tag
    try:
        with open(os.path.join(repo_root, "package.json"), "r", encoding="utf-8") as f:
            pkg = json.load(f)
            v = str(pkg.get("version", "")).strip()
            if v:
                return v
    except Exception:
        pass

    print("Error: TAG could not be determined (set TAG or ensure package.json has a version).", file=sys.stderr)
    sys.exit(1)


def resolve_current_branch(repo_root: str, dry_run: bool) -> str:
    """Resolve the current branch name; prefer GITHUB_REF in CI."""
    github_ref = os.environ.get("GITHUB_REF", "").strip()

    if github_ref:
        if github_ref == "refs/heads/main":
            return "main"
        if re.match(r"^refs/pull/\d+/merge$", github_ref):
            # Merged-PR event in CI: treat as publishable main.
            return "main"

    try:
        branch = (
            subprocess.check_output(
                ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
                timeout=5,
            )
            .decode("utf-8")
            .strip()
        )
        if branch != "unknown":
            return branch
    except Exception:
        pass

    # In a dry run without git / CI ref, default to main so we always produce artifacts.
    return "main" if dry_run else "unknown"


def extract_release_notes_from_changelog(changelog_path: str, tag: str) -> str | None:
    """Extract the first '## <version>' section matching tag from CHANGELOG.md."""
    try:
        text = open(changelog_path, encoding="utf-8").read()
    except FileNotFoundError:
        return None

    heads = [(m.start(), m.group(1)) for m in re.finditer(r"^##\s+([0-9]+\.[0-9]+\.[0-9]+)\s*$", text, re.M)]
    if not heads:
        print("Error: no version sections in CHANGELOG.md", file=sys.stderr)
        return None

    for i, (pos, ver) in enumerate(heads):
        if ver == tag:
            start = pos
            end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
            return text[start:end].rstrip() + "\n"

    print(f"Error: no CHANGELOG section matches version {tag}", file=sys.stderr)
    return None


def find_rollup_bin(repo_root: str) -> str | None:
    """Walk up from repo_root looking for a rollup binary.

    Also probes the agent/image-baked Linux copy at /app/node_modules/.bin/rollup,
    which the unit-test-agents container guarantees even when the repo's own
    node_modules is absent/not mounted (the flush path for loop-release-tests).
    """
    here = repo_root
    while here != "/":
        candidate = os.path.join(here, "node_modules", ".bin", "rollup")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
        here = os.path.dirname(here)
    baked = os.path.join("/app", "node_modules", ".bin", "rollup")
    if os.path.isfile(baked) and os.access(baked, os.X_OK):
        return baked
    return None


def run_build(repo_root: str) -> bool:
    """Build the plugin via rollup. Returns True on success."""
    # Strategy 1: find_rollup_bin -> direct invocation
    rbin = find_rollup_bin(repo_root)
    if rbin:
        print("release.py: building plugin via rollup binary...", file=sys.stderr)
        try:
            subprocess.check_call([rbin, "-c"], cwd=repo_root, stderr=sys.stderr, timeout=180)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Strategy 2: npx rollup
    print("release.py: building plugin via npx rollup...", file=sys.stderr)
    for args in (["npx", "--no-install", "rollup", "-c"], ["npx", "-y", "rollup", "-c"]):
        try:
            subprocess.check_call(args, cwd=repo_root, stderr=sys.stderr, timeout=180)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            continue

    # Strategy 3: npm run build
    print("release.py: building plugin via npm run build...", file=sys.stderr)
    try:
        subprocess.check_call(["npm", "run", "build"], cwd=repo_root, stderr=sys.stderr, timeout=180)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return False


def main() -> int:
    dry_run = os.environ.get("DRY_RUN", "").strip() == "1"
    repo_name = os.environ.get("REPO_NAME", "obsidian-timestamp-utility").strip()
    repo_root = ensure_repo_root()

    # Ensure git safe directory (containerized/rootless scenario).
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", repo_root],
        capture_output=True, timeout=5, check=False,
    )

    tag = resolve_version(repo_root)
    current_branch = resolve_current_branch(repo_root, dry_run)

    print(
        f"release.py: PROJECT_ROOT={repo_root} TAG={tag} REPO_NAME={repo_name} "
        f"DRY_RUN={'1' if dry_run else '0'} branch={current_branch}"
    )

    # MAIN guard.
    if current_branch != "main" and not dry_run:
        print(
            f"release.py: NOT on main ({current_branch}) and DRY_RUN unset -> "
            "skipping publish-prep (exit 0)."
        )
        return 0

    # --- release notes from CHANGELOG.md ---
    changelog_path = os.path.join(repo_root, "CHANGELOG.md")
    if not os.path.isfile(changelog_path):
        print(f"Error: {changelog_path} not found.", file=sys.stderr)
        return 1

    release_notes_text = extract_release_notes_from_changelog(changelog_path, tag)
    if not release_notes_text:
        return 1

    notes_file = os.path.join(repo_root, "release_notes.md")
    os.makedirs(os.path.join(repo_root, "release"), exist_ok=True)
    with open(notes_file, "w", encoding="utf-8") as f:
        f.write(release_notes_text)

    print(f"release.py: wrote {notes_file}", file=sys.stderr)

    # --- build the plugin ---
    if not run_build(repo_root):
        print("Error: plugin build failed (rollup/npm unavailable or errored).", file=sys.stderr)
        return 1

    main_js = os.path.join(repo_root, "dist", "main.js")
    if not os.path.isfile(main_js):
        print("Error: dist/main.js missing after build.", file=sys.stderr)
        return 1

    # --- assemble release files ---
    rel_dir = os.path.join(repo_root, "release")
    for src_name in ["manifest.json", "README.md"]:
        src = os.path.join(repo_root, src_name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(rel_dir, src_name))

    for src_name in ["main.js", "CHANGELOG.md", "release_notes.md"]:
        src = os.path.join(repo_root, "dist", main_js) if src_name == "main.js" else os.path.join(repo_root, src_name)
        if src_name == "main.js":
            src = main_js
        shutil.copy2(src, os.path.join(rel_dir, src_name))

    # --- zip ---
    zip_name = f"{repo_name}-{tag}.zip"
    zip_path = os.path.join(repo_root, zip_name)
    if os.path.isfile(zip_path):
        os.unlink(zip_path)

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for src_name in ["main.js", "manifest.json", "README.md", "CHANGELOG.md", "release_notes.md"]:
                src = os.path.join(rel_dir, src_name)
                if os.path.isfile(src):
                    zf.write(src, arcname=src_name)
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"Error: failed to create zip ({exc}).", file=sys.stderr)
        return 1

    print(f"release.py: artifacts ready in release/ and {zip_name}", file=sys.stderr)
    print("release.py: artifacts ready in release/", file=sys.stdout)

    if dry_run:
        print("release.py: DRY_RUN=1 -> no GitHub release API called.", file=sys.stdout)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
