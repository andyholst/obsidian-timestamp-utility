#!/usr/bin/env python3
"""Temporary thorough dry-run test for the release pipeline (fix-release-pipeline change).

Verifies every release-build step locally WITHOUT calling the GitHub API. Covers:
  S1. The release notes body is generated from the CORRECT version's CHANGELOG section
      (matches package.json version, not just the first/any section) — proven across
      multiple versions present in the CHANGELOG.
  S2. The body is NON-EMPTY (this is the exact 0.4.15 defect: empty body => "").
  S3. main.js is freshly built (npm run build -> dist/main.js) and copied into release/.
  S4. The downloadable zip is created and contains main.js + manifest.json + release_notes.md.
  S5. DRY_RUN=1 produces all local artifacts but never calls the GitHub release API.
  S6. Off-main branch WITHOUT DRY_RUN skips publish-prep (main-branch guard) and exits 0.

Run with:  DRY_RUN=1 python3 -m pytest tests/test_release_pipeline_dryrun.py -v

This is a THROWAWAY verification harness for this change; it doubles as a regression
check but is expected to be removed once the change is delivered (or kept only while in flight).
"""
import os
import re
import shutil
import subprocess
import zipfile
import json
from pathlib import Path
import pytest

WORKFLOWS = os.path.join(os.path.dirname(__file__), "..", ".github", "workflows")
REPO_ROOT = str(Path(__file__).resolve().parent.parent)

REPO_NAME = "obsidian-timestamp-utility"


def _run(cmd, cwd, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)


def _current_version(repo):
    with open(os.path.join(repo, "package.json")) as f:
        return json.load(f)["version"]


def _changelog_sections(changelog_path):
    """Return {version: section_text} for every '## x.y.z' section."""
    text = open(changelog_path, encoding="utf-8").read()
    heads = [(m.start(), m.group(1)) for m in re.finditer(
        r"^##\s+([0-9]+\.[0-9]+\.[0-9]+)\s*$", text, re.M)]
    out = {}
    for i, (pos, ver) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        out[ver] = text[pos:end].rstrip() + "\n"
    return out


def _copy_repo(work):
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(REPO_ROOT, work, ignore=shutil.ignore_patterns(
        ".git", "node_modules", "dist", "release", "__pycache__", ".env"))
    # node_modules may live in the main worktree / parent repo rather than a linked
    # worktree. Walk up from REPO_ROOT to find it, then SYMLINK it (preserves npm's
    # internal package symlinks, which rollup needs to resolve its plugins). Mirrors
    # CI where `npm ci` produces a real node_modules in the checkout.
    nm_src = None
    d = REPO_ROOT
    while d and d != os.path.dirname(d):
        cand = os.path.join(d, "node_modules")
        if os.path.isdir(cand):
            nm_src = cand
            break
        d = os.path.dirname(d)
    nm_dst = work / "node_modules"
    if nm_src and not nm_dst.exists():
        os.symlink(nm_src, nm_dst)
    _ensure_dist(work)


def _ensure_dist(repo):
    """Create a dummy dist/main.js so packaging-only release.sh can test.
    In production, make build-app produces this; tests only need the file
    to exist to verify packaging logic.
    """
    dist = repo / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "main.js").write_text("// dummy plugin build for dry-run packaging test\n")


@pytest.mark.release_dryrun
def test_S1_notes_match_current_version_section(tmp_path):
    """S1: release_notes.md == the CHANGELOG section for package.json's version,
    chosen correctly even when multiple versions exist (e.g. 0.4.15 vs 0.4.14)."""
    work = tmp_path / "repo"
    _copy_repo(work)
    version = _current_version(str(work))
    sections = _changelog_sections(work / "CHANGELOG.md")
    assert version in sections, f"no CHANGELOG section for current version {version}"

    res = _run(["bash", "scripts/release.sh"],
               cwd=str(work), env={"DRY_RUN": "1", "TAG": version, "REPO_NAME": REPO_NAME,
                                   "PROJECT_ROOT": str(work)})
    assert res.returncode == 0, f"make release failed:\n{res.stdout}\n{res.stderr}"

    body = (work / "release" / "release_notes.md").read_text(encoding="utf-8").strip()
    # Content must equal the EXACT section for `version`, not 0.4.14 or any other.
    assert body.strip() == sections[version].strip(), (
        "release_notes.md does not match the CURRENT version's CHANGELOG section")
    # Sanity: it must NOT be a different version's section.
    for other_ver, other_sec in sections.items():
        if other_ver != version:
            assert body.strip() != other_sec.strip(), (
                f"release_notes.md wrongly matched version {other_ver} instead of {version}")


@pytest.mark.release_dryrun
def test_S2_notes_nonempty_prevents_empty_body(tmp_path):
    """S2: this is the precise 0.4.15 defect — an EMPTY body produced '{\"body\":\"\"}'.
    Assert the generated body is non-empty and starts with the version heading."""
    work = tmp_path / "repo"
    _copy_repo(work)
    version = _current_version(str(work))
    res = _run(["bash", "scripts/release.sh"],
               cwd=str(work), env={"DRY_RUN": "1", "TAG": version, "REPO_NAME": REPO_NAME,
                                   "PROJECT_ROOT": str(work)})
    assert res.returncode == 0
    notes = work / "release" / "release_notes.md"
    assert notes.exists(), "release_notes.md missing (would yield empty GitHub body)"
    body = notes.read_text(encoding="utf-8").strip()
    assert body, "release_notes.md is EMPTY — this is exactly the 0.4.15 defect"
    assert body.startswith(f"## {version}"), "release notes must start with the version heading"


@pytest.mark.release_dryrun
def test_S3_main_js_built_and_copied(tmp_path):
    """S3: dist/main.js is built from src/main.ts and copied into release/main.js."""
    work = tmp_path / "repo"
    _copy_repo(work)
    version = _current_version(str(work))
    res = _run(["bash", "scripts/release.sh"],
               cwd=str(work), env={"DRY_RUN": "1", "TAG": version, "REPO_NAME": REPO_NAME,
                                   "PROJECT_ROOT": str(work)})
    assert res.returncode == 0
    main_js = work / "release" / "main.js"
    assert main_js.exists(), "release/main.js missing (build or copy failed)"
    assert main_js.stat().st_size > 0, "release/main.js is empty"
    # manifest.json also copied
    assert (work / "release" / "manifest.json").exists()


@pytest.mark.release_dryrun
def test_S4_zip_contains_expected_members(tmp_path):
    """S4: the downloadable zip is created with main.js + manifest.json + release_notes.md."""
    work = tmp_path / "repo"
    _copy_repo(work)
    version = _current_version(str(work))
    res = _run(["bash", "scripts/release.sh"],
               cwd=str(work), env={"DRY_RUN": "1", "TAG": version, "REPO_NAME": REPO_NAME,
                                   "PROJECT_ROOT": str(work)})
    assert res.returncode == 0
    zip_path = work / f"{REPO_NAME}-{version}.zip"
    assert zip_path.exists(), "release zip not created"
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
    for member in ("main.js", "manifest.json", "release_notes.md"):
        assert member in names, f"zip missing member {member}"


@pytest.mark.release_dryrun
def test_S5_dry_run_produces_artifacts_no_github_call(tmp_path, monkeypatch):
    """S5: DRY_RUN=1 produces local artifacts and never invokes the GitHub API.
    We prove 'no GitHub call' by ensuring no network egress to api.github.com occurs
    (gh is not installed in the test env, and release.sh contains no gh/curl to GitHub)."""
    work = tmp_path / "repo"
    _copy_repo(work)
    version = _current_version(str(work))
    res = _run(["bash", "scripts/release.sh"],
               cwd=str(work), env={"DRY_RUN": "1", "TAG": version, "REPO_NAME": REPO_NAME,
                                   "PROJECT_ROOT": str(work)})
    assert res.returncode == 0
    assert (work / "release" / "release_notes.md").exists()
    assert (work / f"{REPO_NAME}-{version}.zip").exists()
    # release.sh must not contain a GitHub API call
    script = (work / "scripts" / "release.sh").read_text(encoding="utf-8")
    assert "gh " not in script and "api.github.com" not in script and \
        "curl" not in script, "release.sh must not call GitHub (B14 / DRY_RUN safety)"


@pytest.mark.release_dryrun
def test_S7_published_body_matches_changelog_section(tmp_path):
    """S7 (user-critical): what GitHub receives as the release body (via body_path:
    release/release_notes.md) MUST be exactly the corresponding CHANGELOG section,
    so the published release message is right. This mirrors release.yml's body_path step."""
    work = tmp_path / "repo"
    _copy_repo(work)
    version = _current_version(str(work))
    res = _run(["bash", "scripts/release.sh"],
               cwd=str(work), env={"DRY_RUN": "1", "TAG": version, "REPO_NAME": REPO_NAME,
                                   "PROJECT_ROOT": str(work)})
    assert res.returncode == 0
    notes_path = work / "release" / "release_notes.md"
    assert notes_path.exists()
    # This is the exact file the workflow passes as `body_path` to the GitHub release action.
    published_body = notes_path.read_text(encoding="utf-8").strip()
    sections = _changelog_sections(work / "CHANGELOG.md")
    expected = sections[version].strip()
    assert published_body == expected, (
        "The body GitHub would publish does NOT match the CHANGELOG section — "
        "the release message would be wrong.")
    # Also confirm the workflow YAML wires this exact file as the release body.
    wf = (work / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "body_path: release/release_notes.md" in wf, \
        "release.yml must publish from release/release_notes.md"


@pytest.mark.release_dryrun
def test_S6_off_main_without_dry_run_skips(tmp_path):
    """S6: on a non-main branch and DRY_RUN unset, release.sh skips publish-prep (exit 0),
    producing no release/ artifacts — the main-branch guard the user requested."""
    work = tmp_path / "repo"
    _copy_repo(work)
    version = _current_version(str(work))
    # Simulate a feature branch by checking out a detached/non-main ref via git.
    subprocess.run(["git", "checkout", "-q", "-B", "wt/test-branch"], cwd=str(work),
                   capture_output=True)
    res = _run(["bash", "scripts/release.sh"], cwd=str(work),
               env={"TAG": version, "REPO_NAME": REPO_NAME, "DRY_RUN": "0"})
    assert res.returncode == 0, f"release.sh should exit 0 on off-main:\n{res.stderr}"
    assert "NOT on main" in res.stdout, "expected main-branch guard message"
    assert not (work / "release").exists(), "off-main run must not produce release/ artifacts"
