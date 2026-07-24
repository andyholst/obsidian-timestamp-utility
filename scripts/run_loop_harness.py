#!/usr/bin/env python3
"""
run_loop_harness.py — mandatory loop-gate trigger (AGENTS.md behaviour B20).

Thin, honest wrapper over `make loop-harness`. Runs the loop stages IN FULL, then a
FINAL B8 doc-sync gate, in order, and prints a per-stage PASS/FAIL/TIMEOUT summary,
exiting non-zero if any stage is red.

Cross-platform: works identically on macOS (bash 3.2), Linux (bash 4+/5+), and any
POSIX shell that can invoke Python 3. Uses only stdlib: subprocess, signal, time, os,
shutil, argparse, threading.

B8 durable-behaviour range: B1–B32 (the loop's "laws of physics"; see AGENTS.md). The
final check-docs-sync stage FAILS if any sync doc drifts on stage order / loop-ts-floor / B-range.

Canonical stage order (B8 source of truth):
  loop-collect -> loop-ts-floor -> loop-unit -> loop-unit-real -> loop-e2e -> loop-integration -> loop-build-app -> loop-test-app -> loop-release-tests -> loop-secret-scan-tests -> check-docs-sync
"""

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

# ─── Stage definitions ────────────────────────────────────────────────────────

STAGES = [
    "loop-collect",
    "loop-ts-floor",
    "loop-unit",
    "loop-unit-real",
    "loop-e2e",
    "loop-integration",
    "loop-build-app",
    "loop-test-app",
    "loop-release-tests",
    "loop-secret-scan-tests",
    "check-docs-sync",
]

HERMETIC_STAGES = {"loop-collect", "loop-ts-floor", "loop-unit"}

STAGE_TIMEOUTS = {
    "loop-collect": 300,
    "loop-ts-floor": 300,
    "loop-unit": 600,
    "loop-unit-real": 900,
    "loop-e2e": 1200,
    "loop-integration": 1500,
    "loop-build-app": 900,
    "loop-test-app": 900,
    "loop-release-tests": 900,
    "loop-secret-scan-tests": 300,
    "check-docs-sync": 120,
}

STAGE_DESCRIPTIONS = {
    "loop-collect": "pytest --collect-only (unit + integration) via agents.yaml -> fail fast on dangling imports",
    "loop-ts-floor": "scripts/ts_test_floor.sh -> FAIL if describe/leaf/jest-collected/addCommand counts drop below origin/main (silent feature/test removal guard)",
    "loop-unit": "pytest tests/unit (mocked / hermetic) via agents.yaml -> unit-test-agents",
    "loop-unit-real": "pytest tests/unit on LIVE llama (no mocks) via agents.yaml -> unit-test-agents",
    "loop-e2e": "3 standing e2e gates (ticket20 / ticket22 / greetings) via agents.yaml -> integration-test-agents",
    "loop-build-app": "docker compose tools.yaml run app: npm run build (rollup)",
    "loop-test-app": "docker compose tools.yaml run app: npm test (jest)",
    "loop-release-tests": "release-pipeline + README-sync dry-run tests",
    "loop-secret-scan-tests": "secret-scanner pytest suite (real gitleaks, no mocks) containerized via docker-compose-files/gitleaks-tests.yaml (fail-closed)",
    "check-docs-sync": "scripts/check-docs-sync.py -> FAIL if any B8 source-of-truth doc drifts (stage order / loop-ts-floor / B-range B1–B32) — FINAL gate",
}

# ─── Container cleanup helpers ────────────────────────────────────────────────

def _container_cmd():
    """Cached container command."""
    if not hasattr(_container_cmd, "_cached"):
        if shutil.which("nerdctl"):
            _container_cmd._cached = ("nerdctl", ["compose", "-f", "docker-compose-files/agents.yaml"])
        elif shutil.which("docker"):
            _container_cmd._cached = ("docker", ["compose", "-f", "docker-compose-files/agents.yaml"])
        else:
            _container_cmd._cached = (None, None)
    return _container_cmd._cached

def kill_detached(stage):
    """Kill the detached container for a given stage on timeout."""
    svc_map = {
        "loop-integration": "integration-test-agents",
        "loop-build-app": "app",
        "loop-test-app": "app",
    }
    svc = svc_map.get(stage)
    if not svc:
        return
    cmd, args = _container_cmd()
    if cmd is None:
        return
    subprocess.run([cmd, *args, "kill", svc], capture_output=True)
    subprocess.run([cmd, *args, "rm", "-f", svc], capture_output=True)

def stop_loop_containers():
    """Stop containers started by this loop run only."""
    cmd, _ = _container_cmd()
    if cmd is None:
        return

    try:
        result = subprocess.run(
            [cmd, "ps", "-q", "--filter", "label=com.docker.compose.project"],
            capture_output=True, text=True, timeout=30,
        )
        running_now = set(line.strip() for line in result.stdout.strip().splitlines() if line.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return

    marker = Path("/tmp/loop-harness-starting-containers")
    if marker.exists():
        with open(marker) as f:
            running_before = set(line.strip() for line in f.read().strip().splitlines() if line.strip())
        to_stop = running_now - running_before
    else:
        to_stop = running_now

    if to_stop:
        for cid in to_stop:
            subprocess.run([cmd, "stop", cid], capture_output=True)
        print(f"stopped loop-started containers: {len(to_stop)}")
    else:
        print("no loop-started containers to stop.")


# ─── Stage runner ─────────────────────────────────────────────────────────────

def run_stage(stage):
    """
    Run a single stage via `make <stage>` with timeout, tee, and heartbeat.
    Returns (status, elapsed_seconds) where status is 'PASS', 'FAIL', or 'TIMEOUT'.
    """
    timeout_secs = STAGE_TIMEOUTS.get(stage, 600)
    desc = STAGE_DESCRIPTIONS.get(stage, f"make {stage}")

    print(f"=== {stage} (timeout {timeout_secs}s) ===")
    print(f"    [{time.strftime('%H:%M:%S')}] -> {desc}")

    log_path = f"/tmp/loop_{stage}.log"
    rc_file = f"/tmp/loop_rc_{stage}_{os.getpid()}"

    # Clear log and rc file
    Path(log_path).write_text("")
    Path(rc_file).write_text("")

    start_time = time.time()

    # Heartbeat: run in a separate thread to detect if output is flowing
    heartbeat_stop = threading.Event()
    hb_thread = threading.Thread(
        target=_heartbeat,
        args=(log_path, heartbeat_stop),
        daemon=True,
    )
    hb_thread.start()

    # Run with tee-like behavior: line by line to both terminal and log
    final_rc = _run_with_tee(stage, log_path, rc_file, timeout_secs)

    elapsed = time.time() - start_time
    heartbeat_stop.set()
    hb_thread.join(timeout=2)

    if final_rc == 124:
        status = "TIMEOUT"
        kill_detached(stage)
        print(f"  -> TIMEOUT (exceeded {timeout_secs}s); killing detached container")
    elif final_rc != 0:
        status = "FAIL"
        print(f"  -> FAIL (rc={final_rc}; see {log_path})")
    else:
        status = "PASS"
        print(f"  -> PASS")

    print(f"    [{time.strftime('%H:%M:%S')}] elapsed {elapsed:.0f}s")
    return status, elapsed


def _run_with_tee(stage, log_path, rc_file, timeout_secs):
    """Run `make <stage>` with output going to both terminal and log file (line-buffered)."""
    log_fd = open(log_path, "a", buffering=1)  # line-buffered

    try:
        proc = subprocess.Popen(
            ["make", stage],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        while True:
            line = proc.stdout.readline()
            if not line:
                break
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
            log_fd.buffer.write(line)
            log_fd.flush()

        try:
            rc = proc.wait(timeout=timeout_secs)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            rc = 124
    except Exception:
        # If anything goes wrong, default to failure
        rc = 1

    log_fd.close()
    Path(rc_file).write_text(str(rc))
    return rc


def _heartbeat(log_path, stop_event):
    """Background thread that prints heartbeat messages when log file is quiet."""
    last_size = 0
    hb_count = 0
    lp = Path(log_path) if not isinstance(log_path, Path) else log_path

    while not stop_event.is_set():
        stop_event.wait(15)  # sleep 15s, but can be interrupted
        if stop_event.is_set():
            break

        hb_count += 1
        try:
            now_size = lp.stat().st_size
        except FileNotFoundError:
            now_size = 0

        if now_size == last_size:
            print(f"    ... {hb_count * 15}s elapsed (stage quiet, still running)")
            sys.stdout.flush()
        # else: log file grew — output is flowing, no message needed

        last_size = now_size


# ─── Pre-flight ───────────────────────────────────────────────────────────────

def pre_flight():
    """Run B8 doc-sync pre-flight checks."""
    print("=== PRE-FLIGHT 0: check-docs-sync unit tests + live gate ===")
    try:
        subprocess.run(["make", "test-check-docs-sync"], check=True)
    except subprocess.CalledProcessError:
        print("  -> PRE-FLIGHT 0 FAIL: check-docs-sync unit tests failed (gate logic broken)")
        return False

    try:
        subprocess.run(["make", "check-docs-sync"], check=True)
    except subprocess.CalledProcessError:
        print("  -> PRE-FLIGHT 0 FAIL: B8 doc/loop sync drift detected (run from repo root)")
        return False

    print("  -> PRE-FLIGHT 0 PASS")
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run the loop-harness gate")
    parser.add_argument(
        "--hermetic",
        action="store_true",
        help="Only run hermetic stages (loop-collect, loop-ts-floor, loop-unit)",
    )
    args = parser.parse_args()

    # Save starting container list for cleanup
    cmd, _ = _container_cmd()
    if cmd:
        try:
            result = subprocess.run(
                [cmd, "ps", "-q", "--filter", "label=com.docker.compose.project"],
                capture_output=True, text=True, timeout=30,
            )
            Path("/tmp/loop-harness-starting-containers").write_text(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Ensure bind-mount perms
    subprocess.run(["make", "b9-perms"], capture_output=True)

    print("=" * 56)
    print(f" LOOP-HARNESS START — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 56)
    print()

    if not pre_flight():
        print("RESULT: FAILURE — pre-flight B8 doc-sync gate is red. Fix before running stages.")
        sys.exit(1)
    print()

    # Filter stages
    stages = STAGES if not args.hermetic else [s for s in STAGES if s in HERMETIC_STAGES]

    results = {}  # stage -> status

    for stage in stages:
        status, _ = run_stage(stage)
        results[stage] = status

    # Print summary
    print()
    print("=" * 46)
    print(" LOOP-HARNESS SUMMARY")
    print("=" * 46)
    for stage, status in results.items():
        print(f"  {stage:<22s} {status}")
    print("=" * 46)

    any_fail = any(s != "PASS" for s in results.values())
    if not any_fail:
        print("RESULT: ALL RUN STAGES GREEN.")
    else:
        print("RESULT: FAILURE/TIMEOUT — a gate is red. Fix root cause and re-run.")

    # Tear down containers
    stop_loop_containers()

    # Cleanup
    Path("/tmp/loop-harness-starting-containers").unlink(missing_ok=True)

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
