"""Hermetic unit tests for scripts/secret_scanner.py.

These tests verify the PRE-COMMIT / COMMIT-MSG secret-scan logic WITHOUT requiring
a docker runtime, the gitleaks image, or network access. Every test mocks the
gitleaks invocation (``secret_scanner._run_gitleaks``) and the availability probe
(``secret_scanner._available``), so what we exercise is OUR orchestration layer:

  * the public API (scan_text / scan_commit_message / scan_staged_content),
  * fail-closed behaviour when gitleaks cannot run,
  * correct parsing of a gitleaks JSON report (happy + negative),
  * comment-line skipping in commit messages,
  * empty-input short-circuit,
  * the CLI exit codes.

The real gitleaks detection runs in the container (Makefile targets + CI
gitleaks.yml); here we assert our wrapper behaves correctly for every branch the
container path can produce.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "secret_scanner.py"


def _load():
    import sys
    spec = importlib.util.spec_from_file_location("secret_scanner_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["secret_scanner_under_test"] = mod  # needed for dataclass typing
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


# A realistic gitleaks JSON report row (as produced by `gitleaks detect --redact`).
def _row(rule="aws-access-token", match="AKIA********************", line=3,
         file="src/main.ts", secret="AKIA********************"):
    return {"RuleID": rule, "Match": match, "Secret": secret,
            "StartLine": line, "File": file}


# ---------------------------------------------------------------------------
# Helpers: control whether gitleaks "can run" and what its report contains
# ---------------------------------------------------------------------------

@mock.patch.object(MOD, "_available", return_value=True)
@mock.patch.object(MOD, "_run_gitleaks", return_value=[
    MOD.Finding(rule="aws-access-token", match="AKIA********************",
                line=3, file="src/main.ts", severity="HIGH"),
])
def test_scan_text_detects_secret_via_gitleaks(mock_run, mock_avail):
    res = MOD.scan_text("aws_key = AKIAIOSFODNN7EXAMPLE")
    assert res.clean is False
    assert res.engine == "gitleaks"
    assert len(res.findings) == 1
    assert res.findings[0].rule == "aws-access-token"
    assert res.findings[0].line == 3


@mock.patch.object(MOD, "_available", return_value=True)
@mock.patch.object(MOD, "_run_gitleaks", return_value=[])
def test_scan_text_clean_when_gitleaks_reports_nothing(mock_run, mock_avail):
    res = MOD.scan_text("def add(a, b):\n    return a + b\n")
    assert res.clean is True
    assert res.findings == []
    assert res.engine == "gitleaks"


@mock.patch.object(MOD, "_available", return_value=True)
@mock.patch.object(MOD, "_run_gitleaks", return_value=[])
def test_scan_text_empty_input_is_clean(mock_run, mock_avail):
    # Empty / whitespace-only input short-circuits to clean without invoking gitleaks.
    res = MOD.scan_text("")
    assert res.clean is True
    assert res.scanned_chars == 0
    mock_run.assert_not_called()


@mock.patch.object(MOD, "_available", return_value=False)
@mock.patch.object(MOD, "_run_gitleaks", return_value=[
    MOD.Finding(rule="gitleaks-unavailable",
                match="gitleaks could not run ...", severity="HIGH"),
])
def test_fail_closed_when_gitleaks_unavailable(mock_run, mock_avail):
    # Negative / fail-closed: if gitleaks cannot run, the commit MUST be blocked.
    res = MOD.scan_text("anything")
    assert res.clean is False
    assert res.engine == "unavailable"
    assert res.findings[0].rule == "gitleaks-unavailable"


# ---------------------------------------------------------------------------
# Commit-message entry point
# ---------------------------------------------------------------------------

@mock.patch.object(MOD, "_available", return_value=True)
@mock.patch.object(MOD, "_run_gitleaks", return_value=[
    MOD.Finding(rule="aws-access-token", match="AKIA********************", line=1),
])
def test_commit_message_with_secret_rejected(mock_run, mock_avail):
    res = MOD.scan_commit_message("fix: rotate key AKIAIOSFODNN7EXAMPLE")
    assert res.clean is False
    assert "AKIA" in res.findings[0].match or res.findings[0].rule.startswith("aws")


@mock.patch.object(MOD, "_available", return_value=True)
@mock.patch.object(MOD, "_run_gitleaks", return_value=[])
def test_commit_message_clean(mock_run, mock_avail):
    res = MOD.scan_commit_message("feat(scanner): add gitleaks pre-commit hook")
    assert res.clean is True


@mock.patch.object(MOD, "_available", return_value=True)
@mock.patch.object(MOD, "_run_gitleaks", return_value=[])
def test_commit_message_skips_comment_lines(mock_run, mock_avail):
    # '#' comment lines are stripped before scanning; a secret only in a comment
    # must NOT cause a rejection.
    msg = "feat: update\n\n# Example (do not use): AKIAIOSFODNN7EXAMPLE\n"
    res = MOD.scan_commit_message(msg)
    assert res.clean is True
    # Confirm the comment was removed before scanning.
    captured = mock_run.call_args[0][0]
    assert "AKIAIOSFODNN7EXAMPLE" not in captured


# ---------------------------------------------------------------------------
# Staged-content entry point (parses synthetic git diff / blobs)
# ---------------------------------------------------------------------------

def test_scan_staged_content_with_secret():
    # git diff --cached --name-only -> one file; git show :<file> -> a secret blob.
    file_list = subprocess.CompletedProcess(args=[], returncode=0, stdout="src/secret.py\n")
    blob = subprocess.CompletedProcess(args=[], returncode=0,
                                       stdout="password = 'AKIAIOSFODNN7EXAMPLE'\n")
    with mock.patch.object(MOD, "subprocess") as mock_sub, \
         mock.patch.object(MOD, "_run_gitleaks", return_value=[
            MOD.Finding(rule="aws-access-token", match="AKIA********************",
                        line=1, file="src/secret.py", severity="HIGH")]):
        mock_sub.run.side_effect = [file_list, blob]
        res = MOD.scan_staged_content(repo_root=str(REPO_ROOT))
    assert res.clean is False
    assert res.findings[0].file == "src/secret.py"


@mock.patch.object(MOD, "_run_gitleaks", return_value=[])
def test_scan_staged_content_clean(mock_run):
    with mock.patch.object(MOD, "subprocess") as mock_sub:
        file_list = subprocess.CompletedProcess(args=[], returncode=0, stdout="src/clean.py\n")
        blob = subprocess.CompletedProcess(args=[], returncode=0, stdout="x = 1\n")
        mock_sub.run.side_effect = [file_list, blob]
        res = MOD.scan_staged_content(repo_root=str(REPO_ROOT))
    assert res.clean is True


# ---------------------------------------------------------------------------
# Report parsing (the JSON gitleaks emits)
# ---------------------------------------------------------------------------

def test_parses_gitleaks_json_report_via_binary_run(tmp_path, monkeypatch):
    # Force binary mode (so the report path resolves on the host, not /out) and
    # make the mocked subprocess write the gitleaks JSON report there.
    monkeypatch.setenv("GITLEAKS_BIN", "/usr/bin/gitleaks")
    monkeypatch.setattr(MOD, "_runtime", lambda: None)  # force binary mode
    payload = json.dumps([
        _row(rule="aws-access-token", match="AKIA********************", line=7,
             file="a.ts"),
        _row(rule="private-key", match="-----BEGIN PRIVATE KEY-----", line=2,
             file="b.pem"),
    ])
    src = tmp_path / "src.txt"
    src.write_text("x")

    captured = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        if "--report-path" in cmd:
            idx = cmd.index("--report-path")
            report_path = cmd[idx + 1]  # host-real path in binary mode
            with open(report_path, "w", encoding="utf-8") as fh:
                fh.write(payload)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with mock.patch.object(MOD, "subprocess") as mock_sub:
        mock_sub.run.side_effect = _fake_run
        findings = MOD._run_gitleaks(str(src), config=None)
    assert len(findings) == 2
    rules = {f.rule for f in findings}
    assert "aws-access-token" in rules
    assert "private-key" in rules
    assert findings[0].line == 7
    # Binary mode command must use the binary path, not `run <image>`.
    assert "/usr/bin/gitleaks" in captured["cmd"]
    assert "run" not in captured["cmd"]


def test_run_gitleaks_handles_empty_and_malformed_report(tmp_path, monkeypatch):
    monkeypatch.setenv("GITLEAKS_BIN", "/usr/bin/gitleaks")
    monkeypatch.setattr(MOD, "_runtime", lambda: None)  # force binary mode
    src = tmp_path / "s.txt"
    src.write_text("x")

    def _make_writer(content):
        def _fake_run(cmd, **kwargs):
            if "--report-path" in cmd:
                idx = cmd.index("--report-path")
                with open(cmd[idx + 1], "w", encoding="utf-8") as fh:
                    fh.write(content)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        return _fake_run

    with mock.patch.object(MOD, "subprocess") as mock_sub:
        mock_sub.run.side_effect = _make_writer("")
        assert MOD._run_gitleaks(str(src), config=None) == []

    with mock.patch.object(MOD, "subprocess") as mock_sub:
        mock_sub.run.side_effect = _make_writer("{not json")
        assert MOD._run_gitleaks(str(src), config=None) == []


# ---------------------------------------------------------------------------
# CLI exit codes (using --text, with gitleaks mocked)
# ---------------------------------------------------------------------------

@mock.patch.object(MOD, "_available", return_value=True)
@mock.patch.object(MOD, "_run_gitleaks", return_value=[
    MOD.Finding(rule="aws-access-token", match="AKIA********************")])
def test_cli_text_secret_returns_1(mock_run, mock_avail, capsys):
    rc = MOD.main(["--text", "key AKIAIOSFODNN7EXAMPLE"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "SECRET" in err


@mock.patch.object(MOD, "_available", return_value=True)
@mock.patch.object(MOD, "_run_gitleaks", return_value=[])
def test_cli_text_clean_returns_0(mock_run, mock_avail, capsys):
    rc = MOD.main(["--text", "hello world"])
    assert rc == 0
    assert "no secrets detected" in capsys.readouterr().out


def test_cli_requires_a_mode(capsys):
    with pytest.raises(SystemExit):
        MOD.main([])


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------

def test_config_path_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "_repo_root", lambda: str(tmp_path))
    assert MOD._config_path() is None


def test_config_path_finds_gitleaks_toml(tmp_path, monkeypatch):
    (tmp_path / ".gitleaks.toml").write_text("# config\n")
    monkeypatch.setattr(MOD, "_repo_root", lambda: str(tmp_path))
    assert MOD._config_path() == str(tmp_path / ".gitleaks.toml")
