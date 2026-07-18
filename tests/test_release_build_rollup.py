"""Regression test: the release zip MUST contain the compiled plugin (main.js).

This locks the 0.4.16 defect — the GitHub Release published but its zip shipped WITHOUT
dist/main.js because `release.sh` built via `npm run build`, which resolved to `rollup -c`
and failed with "rollup: not found" in CI (rollup not on $PATH after `npm ci`).

The fix: `release.sh` builds via `npx rollup -c` (resolves the local rollup from
node_modules/.bin regardless of $PATH). This test proves that after `npm ci` (i.e. with
node_modules present) a `make release` run produces a non-empty `release/main.js` and a zip
containing `main.js`.

Run with:  DRY_RUN=1 python3 -m pytest tests/test_release_build_rollup.py -v
No GitHub/network calls are made (DRY_RUN=1; release.sh contains no gh/curl).
"""
import os
import shutil
import subprocess
import zipfile
import json
import pytest

REPO_ROOT = subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"], text=True
).strip()
REPO_NAME = "obsidian-timestamp-utility"


def _run(cmd, cwd, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)


def _current_version(repo):
    with open(os.path.join(repo, "package.json")) as f:
        return json.load(f)["version"]


def _copy_repo(work):
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(REPO_ROOT, work, ignore=shutil.ignore_patterns(
        ".git", "dist", "release", "__pycache__"))
    # node_modules may live in the main worktree / parent repo rather than a linked
    # worktree. Walk up from REPO_ROOT to find it, then SYMLINK it (preserves npm's
    # internal package symlinks, which a copytree would break and which rollup needs
    # to resolve its plugins). This mirrors CI where `npm ci` produces a real
    # node_modules in the checkout.
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


@pytest.mark.release_dryrun
def test_release_main_js_built_via_npx(tmp_path):
    """The compiled plugin must be produced (non-empty) into release/main.js."""
    work = tmp_path / "repo"
    _copy_repo(work)
    version = _current_version(str(work))
    res = _run(
        ["bash", "scripts/release.sh"],
        cwd=str(work),
        env={"DRY_RUN": "1", "TAG": version, "REPO_NAME": REPO_NAME},
    )
    assert res.returncode == 0, f"release.sh failed:\n{res.stdout}\n{res.stderr}"
    main_js = work / "release" / "main.js"
    assert main_js.exists(), "release/main.js missing — plugin not bundled (0.4.16 defect)"
    assert main_js.stat().st_size > 0, "release/main.js is empty"
    # dist/main.js must have been produced by rollup
    assert (work / "dist" / "main.js").exists(), "dist/main.js not built by release.sh"


@pytest.mark.release_dryrun
def test_release_zip_contains_main_js(tmp_path):
    """The downloadable zip MUST contain the compiled plugin member `main.js`."""
    work = tmp_path / "repo"
    _copy_repo(work)
    version = _current_version(str(work))
    res = _run(
        ["bash", "scripts/release.sh"],
        cwd=str(work),
        env={"DRY_RUN": "1", "TAG": version, "REPO_NAME": REPO_NAME},
    )
    assert res.returncode == 0, f"release.sh failed:\n{res.stdout}\n{res.stderr}"
    zip_path = work / f"{REPO_NAME}-{version}.zip"
    assert zip_path.exists(), "release zip not created"
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
    assert "main.js" in names, "zip missing main.js — release would ship an unusable plugin"


@pytest.mark.release_dryrun
def test_release_script_uses_npx_not_npm_run_build(tmp_path):
    """Defensive: confirm release.sh builds via npx rollup (the PATH-independent fix)."""
    work = tmp_path / "repo"
    _copy_repo(work)
    script = (work / "scripts" / "release.sh").read_text(encoding="utf-8")
    assert "npx" in script and "rollup" in script, "release.sh must build via npx rollup"
    # The best-effort (build-failure-tolerant) copy of main.js into release/ is gone;
    # the build is now required and main.js is always copied when present.
    assert "release/ will omit main.js" not in script, \
        "release.sh must not silently omit main.js from the release"
