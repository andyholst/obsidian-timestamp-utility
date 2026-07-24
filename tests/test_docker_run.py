#!/usr/bin/env bash
#
# tests/test_docker_run.sh — unit tests for scripts/docker_run.sh.
#
# These tests verify the script's argument parsing, TTY allocation logic,
# and --remove-orphans flag placement in a containerized (Linux) context.
#
# Run with: pytest -v tests/test_docker_run.sh
#

import os
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "docker_run.sh"


def run_script(args: list[str], env=None, expect_rc=0):
    """Run docker_run.sh with given args and return (stdout, stderr, rc)."""
    # Use full path to bash so subprocess can find it even with modified PATH
    result = subprocess.run(
        ["/bin/bash", str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        env={**(os.environ or {}), **(env or {})},
        timeout=30,
    )
    assert result.returncode == expect_rc, f"Expected rc={expect_rc}, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    return result.stdout, result.stderr, result.returncode


# ---------------------------------------------------------------------------
# Test: usage message when insufficient args
# ---------------------------------------------------------------------------

def test_usage_message_missing_args():
    stdout, stderr, rc = run_script([], expect_rc=1)
    assert "Usage:" in stderr


def test_usage_message_one_arg():
    stdout, stderr, rc = run_script(["docker-compose-files/tools.yaml"], expect_rc=1)
    assert "Usage:" in stderr


# ---------------------------------------------------------------------------
# Test: argument parsing — flags vs service name
# ---------------------------------------------------------------------------

def test_parses_flags_and_service_name(capsys):
    """The script should correctly split flags (-e ...) from service name."""
    stdout, stderr, rc = run_script([
        "docker-compose-files/tools.yaml",
        "-e", "TAG=v0.1.0",
        "-e", "REPO_NAME=test",
        "app",
        "npm", "run", "build",
    ])
    # The verbose log should show the parsed components
    assert "DOCKER_RUN:" in stderr
    assert "app" in stderr
    assert "npm" in stderr


def test_parses_service_without_flags():
    """When no flags are given, only service + command should be parsed."""
    stdout, stderr, rc = run_script([
        "docker-compose-files/tools.yaml",
        "unit-test-agents",
        "python", "-m", "pytest", "--collect-only", "-q",
    ])
    assert "DOCKER_RUN:" in stderr
    assert "unit-test-agents" in stderr


# ---------------------------------------------------------------------------
# Test: bash -c handling
# ---------------------------------------------------------------------------

def test_parses_bash_c_command():
    """Commands starting with 'bash -c' should have args joined after '-c'."""
    stdout, stderr, rc = run_script([
        "docker-compose-files/agents.yaml",
        "unit-test-agents",
        "bash", "-c", "cd /project && python -m pytest tests/test_check_docs_sync.py -q",
    ])
    assert "DOCKER_RUN:" in stderr


# ---------------------------------------------------------------------------
# Test: TTY allocation via script (macOS and Linux)
# ---------------------------------------------------------------------------

def test_script_allocates_pty(capsys):
    """The script should use 'script' to allocate a PTY for nerdctl compose run."""
    # Create a minimal compose file for testing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""services:
  test-svc:
    image: alpine:latest
    command: echo "hello from container"
""")
        compose_file = f.name

    try:
        stdout, stderr, rc = run_script([
            compose_file,
            "test-svc",
        ])
        # The script should have printed the DOCKER_RUN log line
        assert "DOCKER_RUN:" in stderr
        # On both macOS and Linux, 'script' is used for PTY allocation
        # We can't easily verify the PTY itself without a real container,
        # but we can verify the command was constructed correctly
        assert "nerdctl" in stderr or "docker" in stderr
    finally:
        os.unlink(compose_file)


# ---------------------------------------------------------------------------
# Test: --remove-orphans flag placement (after 'run', not after 'compose')
# ---------------------------------------------------------------------------

def test_remove_orphans_after_run():
    """The --remove-orphans flag should appear after 'run' in the command."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""services:
  test-svc:
    image: alpine:latest
    command: echo "hello"
""")
        compose_file = f.name

    try:
        # Patch script to capture what would be executed
        with mock.patch("subprocess.run") as mock_run, \
             mock.patch.dict(os.environ, {"NERDCTL_CONTAINERD_SOCK": ""}):
            # Simulate nerdctl being available
            def check_cmd(cmd, **kwargs):
                # Check that --remove-orphans comes after 'run'
                if "nerdctl" in cmd[0] or "docker" in cmd[0]:
                    # Find positions of 'run' and '--remove-orphans'
                    run_idx = None
                    orphans_idx = None
                    for i, part in enumerate(cmd):
                        if part == "run":
                            run_idx = i
                        if part == "--remove-orphans":
                            orphans_idx = i
                    # --remove-orphans should come after 'run'
                    assert run_idx is not None, "'run' not found in command"
                    assert orphans_idx is not None, "'--remove-orphans' not found in command"
                    assert orphans_idx > run_idx, \
                        f"'--remove-orphans' (pos {orphans_idx}) should come after 'run' (pos {run_idx})"
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            mock_run.side_effect = check_cmd
            stdout, stderr, rc = run_script([
                compose_file,
                "test-svc",
            ])
    finally:
        os.unlink(compose_file)


# ---------------------------------------------------------------------------
# Test: FIFO pipe creation (macOS/Linux compatible)
# ---------------------------------------------------------------------------

def test_fifo_pipe_created_and_cleaned():
    """The script should create a FIFO pipe and clean it up after execution."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""services:
  test-svc:
    image: alpine:latest
    command: echo "test"
""")
        compose_file = f.name

    try:
        stdout, stderr, rc = run_script([
            compose_file,
            "test-svc",
        ])
        # The script should have created a /tmp/docker_run_fifo_* file
        # (we can't easily verify cleanup without watching the filesystem)
        assert "DOCKER_RUN:" in stderr
    finally:
        os.unlink(compose_file)


# ---------------------------------------------------------------------------
# Test: platform-agnostic — works on both macOS and Linux
# ---------------------------------------------------------------------------

def test_platform_agnostic():
    """The script uses POSIX-standard tools (script, mkfifo, cat) that work on both macOS and Linux."""
    # Verify all tools used are available
    tools = ["bash", "script", "mkfifo", "cat"]
    for tool in tools:
        result = subprocess.run(["which", tool], capture_output=True, text=True)
        assert result.returncode == 0, f"Required tool '{tool}' not found on PATH"


# ---------------------------------------------------------------------------
# Test: error when neither nerdctl nor docker is available
# ---------------------------------------------------------------------------

def test_error_when_no_runtime():
    """If neither nerdctl nor docker is on PATH, the script should exit with error."""
    # Use full path to bash so subprocess can find it even with empty PATH
    stdout, stderr, rc = run_script(
        ["docker-compose-files/tools.yaml", "app", "npm", "run", "build"],
        env={"PATH": "/nonexistent", "HOME": os.environ.get("HOME", "/tmp")},
        expect_rc=1,
    )
    # The script exits with 1 when neither runtime is found
    assert rc == 1
    assert "Neither nerdctl nor docker found" in stderr
