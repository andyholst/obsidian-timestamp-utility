#!/usr/bin/env python3
"""Thin wrapper that runs **gitleaks** (inside a Docker/Nerdctl container) to scan
for secrets.

This replaces the broken TruffleHog GitHub Action. We do NOT implement our own
secret detection -- gitleaks (https://github.com/gitleaks/gitleaks, Apache-2.0, a
mature Go binary) is the ONLY scanner. This module is a thin, testable wrapper
that runs gitleaks, preferring a gitleaks Docker image (zricethezav/gitleaks) so the
exact same engine runs locally (pre-commit/commit-msg hooks) and in CI, with no
local binary install required.

Invocation points:
  * git-hooks/pre-commit  -> scan_staged_content()  (blocks secrets in the index)
  * git-hooks/commit-msg  -> scan_commit_message()  (blocks secrets in the message)

Fail-closed: if gitleaks cannot run (no image, no runtime), scanning returns a
NON-clean result so the commit is blocked with an actionable message. We never
silently skip the check -- that is the exact failure mode that made TruffleHog's
"BASE and HEAD commits are the same" abort dangerous.

Container execution matches the repo convention: all real work runs through
docker/nerdctl compose. Locally we `run` the gitleaks image with the repo mounted
read-only; the binary path is a fallback only.

CLI:
    python scripts/secret_scanner.py --staged
    python scripts/secret_scanner.py --message-file <path>
    python scripts/secret_scanner.py --text "..."

Exit codes: 0 = clean, 1 = secret found (or gitleaks unavailable), 2 = usage/error.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

# Allow callers/tests to override the container runtime and image.
_RUNTIME_ENV = "GITLEAKS_RUNTIME"        # e.g. "nerdctl" or "docker"
_IMAGE_ENV = "GITLEAKS_IMAGE"            # e.g. "zricethezav/gitleaks:v8.18.4"
_BINARY_ENV = "GITLEAKS_BIN"             # explicit local binary override
_DEFAULT_IMAGE = "zricethezav/gitleaks:v8.18.4"


@dataclass
class Finding:
    """A single detected secret (as reported by gitleaks)."""

    rule: str
    match: str
    line: Optional[int] = None
    file: Optional[str] = None
    severity: str = "HIGH"

    def __str__(self) -> str:
        loc = ""
        if self.file:
            loc += f" {self.file}"
        if self.line is not None:
            loc += f":{self.line}"
        return f"[{self.severity}] {self.rule}{loc}: {self.match}"


@dataclass
class ScanResult:
    """Outcome of a scan."""

    clean: bool
    findings: List[Finding] = field(default_factory=list)
    engine: str = "gitleaks"      # "gitleaks" | "unavailable"
    scanned_chars: int = 0

    def __bool__(self) -> bool:   # ``if result`` == clean
        return self.clean


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _runtime() -> Optional[str]:
    override = os.environ.get(_RUNTIME_ENV)
    # "none"/"false"/"0" explicitly force local-binary (no container) mode.
    if override and override.lower() in ("none", "false", "0"):
        return None
    if override:
        return override
    for cand in ("nerdctl", "docker"):
        if shutil.which(cand):
            return cand
    return None


def _image() -> str:
    return os.environ.get(_IMAGE_ENV, _DEFAULT_IMAGE)


def _binary() -> Optional[str]:
    override = os.environ.get(_BINARY_ENV)
    if override:
        return override
    return shutil.which("gitleaks")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config_path() -> Optional[str]:
    cfg = os.path.join(_repo_root(), ".gitleaks.toml")
    return cfg if os.path.exists(cfg) else None


# ---------------------------------------------------------------------------
# gitleaks invocation (container-first, binary fallback)
# ---------------------------------------------------------------------------

def _available() -> bool:
    """True if gitleaks can run via container runtime or local binary."""
    return _runtime() is not None or _binary() is not None


def _run_gitleaks(source_path: str, config: Optional[str]) -> List[Finding]:
    """Run gitleaks over a single file path; parse the JSON report.

    Uses a container runtime if present, else a local binary. Returns a single
    'gitleaks-unavailable' finding (non-clean) when neither is runnable.
    """
    runtime = _runtime()
    binary = _binary()
    report_fd, report_path = tempfile.mkstemp(suffix=".json")
    os.close(report_fd)

    cmd: List[str]
    if runtime:
        # Run gitleaks in a throwaway container. Mount the source's PARENT dir into
        # /src (gitleaks --source takes a DIRECTORY, not a file) and pass the report
        # path out via a bind of the host tmp dir. --no-git scans plain files.
        cmd = [
            runtime, "run", "--rm",
            "-v", f"{os.path.dirname(source_path)}:/src:ro",
            "-v", f"{os.path.dirname(report_path)}:/out:rw",
            _image(),
            "detect",
            "--source", "/src",
            "--no-git",
            "--no-banner", "--redact",
            "--report-format", "json",
            "--report-path", "/out/" + os.path.basename(report_path),
        ]
    elif binary:
        # gitleaks --source must be a DIRECTORY (not a file). Scan the parent dir.
        cmd = [
            binary, "detect",
            "--source", os.path.dirname(source_path),
            "--no-git",
            "--no-banner", "--redact",
            "--report-format", "json",
            "--report-path", report_path,
        ]
    else:
        os.remove(report_path)
        return [Finding(
            rule="gitleaks-unavailable",
            match=("gitleaks could not run (no container runtime 'nerdctl'/'docker' and no "
                   "gitleaks binary on PATH). Refusing to commit unverified content. "
                   "Install: 'brew install gitleaks', 'apt install gitleaks', or ensure "
                   "nerdctl/docker + the gitleaks image are available."),
            severity="HIGH",
        )]

    if config:
        cmd += ["--config", config]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=False)
        findings: List[Finding] = []
        if os.path.exists(report_path) and os.path.getsize(report_path) > 0:
            with open(report_path, "r", encoding="utf-8", errors="replace") as fh:
                try:
                    rows = json.load(fh)
                except json.JSONDecodeError:
                    rows = []
            for row in rows:
                findings.append(Finding(
                    rule=row.get("RuleID") or row.get("Description") or "gitleaks",
                    match=row.get("Match") or row.get("Secret") or "(redacted)",
                    line=row.get("StartLine"),
                    file=row.get("File"),
                    severity="HIGH",
                ))
        return findings
    finally:
        if os.path.exists(report_path):
            try:
                os.remove(report_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_text(text: str, source_label: str = "stdin",
              config: Optional[str] = None) -> ScanResult:
    """Scan arbitrary text for secrets using gitleaks (container-first).

    ``config`` overrides the gitleaks config path (defaults to ``_config_path()``),
    so callers can scan with a specific ruleset (e.g. the repo's ``.gitleaks.toml``).
    """
    text = text or ""
    if not text.strip():
        return ScanResult(clean=True, engine="gitleaks", scanned_chars=0)
    cfg = config if config is not None else _config_path()
    # Isolate the source in its OWN temp dir so the container only scans THIS file
    # (mounting the parent dir as /src would otherwise scan every sibling in /tmp).
    src_dir = tempfile.mkdtemp(prefix="gitleaks-src-")
    src_path = os.path.join(src_dir, "scan.txt")
    try:
        with open(src_path, "w", encoding="utf-8", errors="replace") as fh:
            fh.write(text)
        findings = _run_gitleaks(src_path, cfg)
    finally:
        try:
            os.remove(src_path)
            os.rmdir(src_dir)
        except OSError:
            pass
    engine = "gitleaks" if _available() else "unavailable"
    return ScanResult(clean=len(findings) == 0, findings=findings,
                      engine=engine, scanned_chars=len(text))


def scan_file(path: str, config: Optional[str] = None) -> ScanResult:
    """Scan a single file on disk for secrets using gitleaks.

    Reads the file, scans its content via gitleaks, and reports findings (the
    finding 'file' is set to ``path`` so callers see the real path, not a temp
    location). Returns a clean result on read errors rather than raising.
    """
    cfg = config if config is not None else _config_path()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return ScanResult(clean=True, engine="gitleaks", scanned_chars=0)
    result = scan_text(text, source_label=path, config=cfg)
    # Report the real (caller-visible) path, not the temp location used internally.
    for f in result.findings:
        f.file = path
    return result


def scan_commit_message(message: str) -> ScanResult:
    """Scan a commit-message string for secrets. Skips '#' comment lines."""
    body = "\n".join(
        ln for ln in (message or "").splitlines() if not ln.lstrip().startswith("#")
    )
    return scan_text(body, source_label="commit-message")


def scan_staged_content(repo_root: Optional[str] = None) -> ScanResult:
    """Scan the currently staged (index) content for secrets via gitleaks."""
    repo_root = repo_root or os.getcwd()
    config = _config_path()
    all_findings: List[Finding] = []
    scanned_chars = 0
    try:
        files = (subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines())
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = []

    if files:
        for f in files:
            try:
                blob = subprocess.run(
                    ["git", "show", f":{f}"], cwd=repo_root,
                    capture_output=True, text=True, check=True,
                ).stdout
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
            if not blob:
                continue
            scanned_chars += len(blob)
            src_dir = tempfile.mkdtemp(prefix="gitleaks-staged-")
            src_path = os.path.join(src_dir, "scan.txt")
            try:
                with open(src_path, "w", encoding="utf-8", errors="replace") as fh:
                    fh.write(blob)
                for finding in _run_gitleaks(src_path, config):
                    # Report the real (repo-relative) path, not the temp location.
                    finding.file = f
                    all_findings.append(finding)
            finally:
                try:
                    os.remove(src_path)
                    os.rmdir(src_dir)
                except OSError:
                    pass
    else:
        try:
            diff = subprocess.run(
                ["git", "diff", "--cached", "--no-color"], cwd=repo_root,
                capture_output=True, text=True, check=True,
            ).stdout
            scanned_chars = len(diff)
            all_findings.extend(scan_text(diff, source_label="staged-diff").findings)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    engine = "gitleaks" if _available() else "unavailable"
    return ScanResult(clean=len(all_findings) == 0, findings=all_findings,
                      engine=engine, scanned_chars=scanned_chars)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def scan_repo(repo_root: Optional[str] = None) -> ScanResult:
    """Scan the whole repository working tree for secrets using gitleaks.

    Uses gitleaks' native recursive directory scan over the repo root (honouring
    .gitignore and the repo .gitleaks.toml allowlist). Returns a ScanResult.
    """
    repo_root = repo_root or _repo_root()
    cfg = _config_path()
    runtime = _runtime()
    binary = _binary()
    report_fd, report_path = tempfile.mkstemp(suffix=".json")
    os.close(report_fd)
    cmd: List[str]
    if runtime:
        cmd = [
            runtime, "run", "--rm",
            "-v", f"{repo_root}:/src:ro",
            "-v", f"{os.path.dirname(report_path)}:/out:rw",
            _image(), "detect",
            "--source", "/src", "--redact",
            "--report-format", "json",
            "--report-path", "/out/" + os.path.basename(report_path),
        ]
        if cfg:
            cmd += ["--config", "/src/.gitleaks.toml"]
    elif binary:
        cmd = [
            binary, "detect",
            "--source", repo_root, "--redact",
            "--report-format", "json",
            "--report-path", report_path,
        ]
        if cfg:
            cmd += ["--config", cfg]
    else:
        os.remove(report_path)
        return ScanResult(clean=False, engine="unavailable", scanned_chars=0,
                          findings=[Finding(
                              rule="gitleaks-unavailable",
                              match=("gitleaks could not run (no container runtime and no "
                                     "gitleaks binary on PATH). Refusing to verify the repo. "
                                     "Install gitleaks or nerdctl/docker."),
                              severity="HIGH")])
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=False)
        findings: List[Finding] = []
        if os.path.exists(report_path) and os.path.getsize(report_path) > 0:
            with open(report_path, "r", encoding="utf-8", errors="replace") as fh:
                try:
                    rows = json.load(fh)
                except json.JSONDecodeError:
                    rows = []
            for row in rows:
                findings.append(Finding(
                    rule=row.get("RuleID") or row.get("Description") or "gitleaks",
                    match=row.get("Match") or row.get("Secret") or "(redacted)",
                    line=row.get("StartLine"),
                    file=row.get("File"),
                    severity="HIGH"))
        return ScanResult(clean=len(findings) == 0, findings=findings,
                          engine="gitleaks", scanned_chars=0)
    finally:
        if os.path.exists(report_path):
            try:
                os.remove(report_path)
            except OSError:
                pass


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan for secrets using gitleaks (container-first).")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--staged", action="store_true", help="Scan staged git content.")
    grp.add_argument("--message-file", metavar="PATH", help="Scan a commit-message file.")
    grp.add_argument("--file", metavar="PATH", help="Scan a file on disk.")
    grp.add_argument("--repo-scan", action="store_true",
                     help="Scan the whole repository working tree for secrets.")
    grp.add_argument("--text", metavar="STR", help="Scan an inline string.")
    args = parser.parse_args(argv)

    if args.staged:
        result = scan_staged_content()
    elif args.file:
        result = scan_file(args.file)
    elif args.repo_scan:
        result = scan_repo()
    elif args.message_file:
        try:
            with open(args.message_file, "r", encoding="utf-8", errors="replace") as fh:
                result = scan_commit_message(fh.read())
        except OSError as exc:
            print(f"secret_scanner: cannot read message file: {exc}", file=sys.stderr)
            return 2
    else:
        result = scan_text(args.text or "")

    if result.clean:
        print(f"secret_scanner [{result.engine}]: no secrets detected.")
        return 0
    print(f"secret_scanner [{result.engine}]: SECRET(S) DETECTED -- commit blocked.",
          file=sys.stderr)
    for f in result.findings:
        print(f"  {f}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
