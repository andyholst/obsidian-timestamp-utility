#!/usr/bin/env python3
"""README-sync divergence test (fix-release-pipeline change, extends B17a).

The README is a user-facing doc that MUST stay in sync with the shipped code and the
other source-of-truth files. This test detects divergences WITHOUT calling GitHub:

  R1. README "Current plugin version: **X.Y.Z**" equals package.json version.
  R2. README release tag `vX.Y.Z` equals the version (no stale tag like v0.4.11 on a 0.4.15 tree).
  R3. The top CHANGELOG.md section version equals the README/package.json version (all three agree).
  R4. Every plugin command id declared in src/main.ts (this.addCommand({ id: '...' }))
      is referenced somewhere in the README (a new command must be documented).
  R5. README links to CHANGELOG.md / AGENTS.md resolve to real files in the repo.

Run with:  python3 -m pytest tests/test_readme_sync.py -v
(Hermetic; part of the loop gate via `loop-release-tests` once wired, or standalone.)
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(
    __file__).resolve().parent.parent


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_R1_readme_version_matches_package_json():
    readme = _read(REPO_ROOT / "README.md")
    pkg = json.loads(_read(REPO_ROOT / "package.json"))
    ver = pkg["version"]
    # README carries "Current plugin version: **X.Y.Z**"
    m = re.search(r"Current plugin version:\s*\*\*([0-9]+\.[0-9]+\.[0-9]+)\*\*", readme)
    assert m, "README missing 'Current plugin version: **X.Y.Z**' marker"
    readme_ver = m.group(1)
    assert readme_ver == ver, (
        f"README version {readme_ver} != package.json version {ver} "
        f"(stale README — this is exactly the 0.4.11-vs-0.4.15 drift)")


def test_R2_readme_release_tag_matches_version():
    readme = _read(REPO_ROOT / "README.md")
    pkg = json.loads(_read(REPO_ROOT / "package.json"))
    ver = pkg["version"]
    # README tag marker: tag `vX.Y.Z`
    m = re.search(r"tag\s+`v([0-9]+\.[0-9]+\.[0-9]+)`", readme)
    assert m, "README missing 'tag `vX.Y.Z`' marker"
    assert m.group(1) == ver, f"README tag v{m.group(1)} != version {ver}"


def test_R3_changelog_top_version_agrees_with_readme():
    readme = _read(REPO_ROOT / "README.md")
    changelog = _read(REPO_ROOT / "CHANGELOG.md")
    top = re.search(r"^##\s+([0-9]+\.[0-9]+\.[0-9]+)\s*$", changelog, re.M)
    assert top, "CHANGELOG.md has no version section heading"
    rm = re.search(r"Current plugin version:\s*\*\*([0-9]+\.[0-9]+\.[0-9]+)\*\*", readme)
    assert rm, "README missing version marker"
    assert top.group(1) == rm.group(1), (
        f"CHANGELOG top version {top.group(1)} != README version {rm.group(1)}")


def test_R4_all_plugin_commands_documented_in_readme():
    main_ts = _read(REPO_ROOT / "src/main.ts")
    readme = _read(REPO_ROOT / "README.md")
    # README documents commands by their human-readable `name:`, not the `id:`.
    names = re.findall(r"this\.addCommand\(\{\s*id:\s*'[^']+'\s*,\s*name:\s*'([^']+)'", main_ts)
    assert names, "no addCommand names found in src/main.ts"
    # Each command name should appear (substring) in the README Commands section.
    undocumented = [n for n in names if n not in readme]
    assert not undocumented, f"README does not document plugin command(s): {undocumented}"


def test_R5_readme_links_to_source_files_resolve():
    readme = _read(REPO_ROOT / "README.md")
    link_targets = re.findall(r"\]\(([^)]+\.md)\)", readme)
    missing = []
    for t in link_targets:
        if t.startswith("http"):
            continue
        p = REPO_ROOT / t
        if not p.exists():
            missing.append(t)
    assert not missing, f"README links to non-existent files: {missing}"
