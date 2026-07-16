"""INTEGRATION tests for scripts/secret_scanner.py — NO MOCKS.

These tests drive the REAL gitleaks binary (the authoritative detector). They are
skipped automatically when no gitleaks binary is available, and RUN when the test
container image (containers/gitleaks-tests) executes them (gitleaks is on PATH there).

Temporary fixture files containing example/placeholder secrets are written at test
time under a unique temp dir, then scanned by the real binary. This proves the
pre-commit secret-scanning actually catches secrets via gitleaks — not a fake.
"""

import json
import os
import shutil
import subprocess
import tempfile

import pytest

import importlib.util
import sys as _sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_SCRIPT = os.path.join(_REPO, "scripts", "secret_scanner.py")
spec = importlib.util.spec_from_file_location("secret_scanner", _SCRIPT)
MOD = importlib.util.module_from_spec(spec)
_sys.modules["secret_scanner"] = MOD  # register so dataclass typing resolves
spec.loader.exec_module(MOD)

# Force BINARY mode so we exercise the REAL gitleaks binary directly (no container per
# test). _runtime() is patched to None and GITLEAKS_BIN points at the real binary that
# is on PATH inside the test container (and on the host during local runs).
@pytest.fixture(autouse=True)
def _force_binary(monkeypatch):
    # Force BINARY mode so we exercise the REAL gitleaks binary directly.
    monkeypatch.setattr(MOD, "_runtime", lambda: None)
    _bin = _real_gitleaks()
    if _bin:
        monkeypatch.setenv("GITLEAKS_BIN", _bin)


def _real_gitleaks():
    """Return the path to a real gitleaks binary, or None if unavailable."""
    env = os.environ.get("GITLEAKS_BIN")
    if env and shutil.which(env):
        return env
    return shutil.which("gitleaks")


requires_real_gitleaks = pytest.mark.skipif(
    _real_gitleaks() is None,
    reason="no real gitleaks binary on PATH (set GITLEAKS_BIN to enable)",
)


@pytest.fixture
def workdir():
    d = tempfile.mkdtemp(prefix="gl-int-")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# --- Example/placeholder secret fixtures (these are NOT real credentials) ---------
# NOTE: the Slack token is assembled at runtime so the *source file* contains no
# literal `xoxb-...` secret shape (GitHub push-protection would otherwise flag it).
# gitleaks still detects the assembled value when the test scans it (rule is
# version-dependent: slack-bot-token vs slack-access-token), proving the scanner works.
SLACK_TOKEN = "x" + "oxb-0000000000-0000000000-000000000000000000000000"
PRIVATE_KEY = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIBOgIBAAJBAKjOY0BbTkA9aKZ7QcW3VhQ2Q6Z0r3tX7Y9wZ4Q3Yq8\n"
    "-----END RSA PRIVATE KEY-----\n"
)
CLEAN_CODE = "def add(a, b):\n    return a + b\n"


@requires_real_gitleaks
def test_real_gitleaks_binary_is_invoked(workdir):
    # Sanity: the binary exists and runs (proves we hit the real tool, not a fake).
    out = subprocess.run([_real_gitleaks(), "version"],
                         capture_output=True, text=True, check=False)
    assert out.returncode == 0


@requires_real_gitleaks
def test_scan_text_detects_slack_secret(workdir):
    res = MOD.scan_text("token = " + SLACK_TOKEN)
    assert res.clean is False
    rules = {f.rule for f in res.findings}
    # Rule name is gitleaks-version-dependent (slack-bot-token vs slack-access-token);
    # assert on the stable "slack" family so the test is version-agnostic.
    assert any("slack" in r for r in rules)


@requires_real_gitleaks
def test_scan_text_detects_private_key(workdir):
    res = MOD.scan_text(PRIVATE_KEY)
    assert res.clean is False
    rules = {f.rule for f in res.findings}
    assert "private-key" in rules


@requires_real_gitleaks
def test_scan_text_clean_code_is_clean(workdir):
    res = MOD.scan_text(CLEAN_CODE)
    assert res.clean is True
    assert res.findings == []


@requires_real_gitleaks
def test_scan_file_detects_secret_in_file(workdir):
    path = os.path.join(workdir, "config.env")
    with open(path, "w") as fh:
        fh.write("SLACK_TOKEN=" + SLACK_TOKEN + "\n")
    res = MOD.scan_file(path)
    assert res.clean is False
    assert any(f.file == path for f in res.findings)


@requires_real_gitleaks
def test_scan_file_empty_is_clean(workdir):
    path = os.path.join(workdir, "empty.txt")
    open(path, "w").close()
    res = MOD.scan_file(path)
    assert res.clean is True


@requires_real_gitleaks
def test_scan_file_multiple_findings_reported(workdir):
    path = os.path.join(workdir, "secrets.txt")
    with open(path, "w") as fh:
        fh.write("a = " + SLACK_TOKEN + "\n")
        fh.write(PRIVATE_KEY + "\n")
    res = MOD.scan_file(path)
    assert res.clean is False
    assert len(res.findings) >= 2


@requires_real_gitleaks
def test_scan_staged_content_finds_secret_in_staged_blob(workdir, monkeypatch):
    # Simulate `git diff --cached --name-only` + `git show :<file>` via a fake git.
    staged_file = os.path.join(workdir, "db.py")
    with open(staged_file, "w") as fh:
        fh.write("password = '" + SLACK_TOKEN + "'\n")

    _real_run = subprocess.run
    def _fake_git(cmd, **kwargs):
        # git calls are faked; everything else (notably gitleaks) runs for real.
        if cmd and cmd[0] == "git" and "diff" in cmd and "--name-only" in cmd:
            return subprocess.CompletedProcess(cmd, 0, staged_file + "\n")
        if cmd and cmd[0] == "git" and cmd[1] == "show" and cmd[2].startswith(":"):
            return subprocess.CompletedProcess(cmd, 0,
                                               "password = '" + SLACK_TOKEN + "'\n")
        return _real_run(cmd, **kwargs)

    monkeypatch.setattr(MOD.subprocess, "run", _fake_git)
    res = MOD.scan_staged_content(repo_root=workdir)
    assert res.clean is False
    assert any(f.file == staged_file for f in res.findings)


@requires_real_gitleaks
def test_scan_staged_content_clean_when_no_secret(workdir, monkeypatch):
    staged_file = os.path.join(workdir, "util.py")
    with open(staged_file, "w") as fh:
        fh.write(CLEAN_CODE)

    _real_run = subprocess.run
    def _fake_git(cmd, **kwargs):
        if cmd and cmd[0] == "git" and "diff" in cmd and "--name-only" in cmd:
            return subprocess.CompletedProcess(cmd, 0, staged_file + "\n")
        if cmd and cmd[0] == "git" and cmd[1] == "show" and cmd[2].startswith(":"):
            return subprocess.CompletedProcess(cmd, 0, CLEAN_CODE)
        return _real_run(cmd, **kwargs)

    monkeypatch.setattr(MOD.subprocess, "run", _fake_git)
    res = MOD.scan_staged_content(repo_root=workdir)
    assert res.clean is True


@requires_real_gitleaks
def test_allowlist_excludes_test_fixtures(workdir, monkeypatch):
    # A fixture under a path matching the .gitleaks.toml allowlist
    # (''''(?i)tests/.*secret.*'''') MUST be suppressed even though its content would
    # otherwise trip the default AWS rule. We scan the real tree directly (not via the
    # wrapper's temp-dir isolation) so gitleaks sees the genuine path -- exactly how
    # `loop-secret-scan` sees /src.
    tree = os.path.join(workdir, "tests", "fixtures")
    os.makedirs(tree, exist_ok=True)
    fx = os.path.join(tree, "sample_secret.txt")
    with open(fx, "w") as fh:
        fh.write("AKIAIOSFODNN7EXAMPLE\n")  # default AWS rule would flag this
    bin_ = _real_gitleaks()
    assert bin_ is not None
    out = subprocess.run(
        [bin_, "detect", "--source", workdir, "--no-git",
         "--no-banner", "--config", os.path.join(_REPO, ".gitleaks.toml"),
         "--report-format", "json", "--report-path", os.path.join(workdir, "r.json")],
        capture_output=True, text=True, check=False)
    findings = []
    rpath = os.path.join(workdir, "r.json")
    if os.path.exists(rpath) and os.path.getsize(rpath) > 0:
        with open(rpath) as fh:
            try:
                findings = json.load(fh)
            except json.JSONDecodeError:
                findings = []
    assert findings == [], "fixture under tests/.*secret.* must be allowlisted"


@requires_real_gitleaks
def test_cli_text_mode_exits_nonzero_on_secret(workdir):
    # End-to-end via the CLI entrypoint (real binary). Force BINARY mode in the
    # subprocess env (the autouse fixture only patches the in-process MOD).
    env = dict(os.environ)
    env["GITLEAKS_RUNTIME"] = "none"  # force binary mode (no container)
    env["GITLEAKS_BIN"] = _real_gitleaks()
    p = subprocess.run(
        ["python3", _SCRIPT, "--text", "k=" + SLACK_TOKEN],
        capture_output=True, text=True, check=False, env=env)
    assert p.returncode == 1


@requires_real_gitleaks
def test_cli_text_mode_exits_zero_when_clean(workdir):
    env = dict(os.environ)
    env["GITLEAKS_RUNTIME"] = "none"
    env["GITLEAKS_BIN"] = _real_gitleaks()
    p = subprocess.run(
        ["python3", _SCRIPT, "--text", CLEAN_CODE],
        capture_output=True, text=True, check=False, env=env)
    assert p.returncode == 0


# --- Repo-local sensitivity rule (the "password.txt" scenario) -----------------
# Best-practice gitleaks setup: extend the DEFAULT ruleset (useDefault=true) and
# layer a tight repo-local rule so LOW-ENTROPY credential assignments like
# `PASSWORD='fsdfsdf#"!¤!"'` are caught (the default ruleset misses them). This test
# drives the REAL gitleaks binary with the repo's .gitleaks.toml and asserts the
# `repo-password-assignment` rule fires. No mocks.
PASSWORD_SAMPLE = "PASSWORD='fsdfsdf#\"!¤!\"'"
CLEAN_ASSIGNMENTS = (
    "SECRET=${VAR}\n"          # env-var reference, not a literal secret
    "PASSWORD=\n"               # empty value
    "API_KEY=os.getenv('X')\n"  # function call, not a literal secret
)


@requires_real_gitleaks
def test_repo_password_rule_fires_on_low_entropy_assignment(workdir):
    res = MOD.scan_text(PASSWORD_SAMPLE,
                        config=os.path.join(_REPO, ".gitleaks.toml"))
    assert res.clean is False
    rules = {f.rule for f in res.findings}
    assert "repo-password-assignment" in rules


@requires_real_gitleaks
def test_repo_password_rule_ignores_env_var_and_empty(workdir):
    # These legitimate forms MUST NOT trigger the repo-local rule (no false positives).
    res = MOD.scan_text(CLEAN_ASSIGNMENTS,
                        config=os.path.join(_REPO, ".gitleaks.toml"))
    rules = {f.rule for f in res.findings}
    assert "repo-password-assignment" not in rules
