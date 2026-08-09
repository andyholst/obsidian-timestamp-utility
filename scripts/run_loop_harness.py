#!/usr/bin/env python3
"""run_loop_harness.py — mandatory loop-gate trigger (AGENTS.md behaviour B20).

Thin, honest wrapper over the Makefile loop-harness stages. Runs all stages IN FULL,
then a FINAL B8 doc-sync gate, in order:

  loop-collect -> loop-ts-floor -> loop-unit -> loop-unit-real -> loop-e2e -> loop-integration
  -> loop-build-app -> loop-test-app -> loop-release-tests -> loop-secret-scan-tests -> check-docs-sync

Prints a per-stage PASS/FAIL/TIMEOUT summary and exits non-zero if any stage is red.

Ollama is expected to be running on the host (bound to 127.0.0.1:11434) and is reachable
from the containers via network_mode: host. ALL stages run for real. If a stage fails
OR hangs past its timeout, the script reports FAIL/TIMEOUT and exits non-zero; fix the
root cause and re-run. Do NOT fake-green.

B8 durable-behaviour range: B1–B32 (the loop's "laws of physics"; see AGENTS.md). The
final check-docs-sync stage FAILS if any sync doc drifts on stage order / loop-ts-floor / B-range.

Usage:
    python3 scripts/run_loop_harness.py              # full loop-harness (all stages)
    python3 scripts/run_loop_harness.py --hermetic   # only loop-collect + loop-unit (fast pre-flight)
"""
from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
import time


# Canonical stage order (B8 source of truth) — MUST match AGENTS.md / Makefile.
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

# Per-stage wall-clock caps (seconds). Generous but finite; a hung stage must not block forever.
STAGE_TIMEOUT: dict[str, int] = {
    "loop-collect": 600,
    "loop-ts-floor": 300,
    "loop-unit": 1200,
    "loop-unit-real": 1800,
    "loop-e2e": 2400,
    "loop-integration": 2700,
    "loop-build-app": 900,
    "loop-test-app": 900,
    "loop-release-tests": 600,
    "loop-secret-scan-tests": 300,
    "check-docs-sync": 120,
}

# Human-readable description of what each stage drives (shown in the start banner).
STAGE_DESC: dict[str, str] = {
    "loop-collect": "pytest --collect-only (unit + integration) via agents.yaml — fail fast on dangling imports",
    "loop-ts-floor": "scripts/ts_test_floor.py — FAIL if describe/leaf/jest-collected/addCommand counts drop below origin/main (silent feature/test removal guard)",
    "loop-unit": "pytest tests/unit (mocked / hermetic) via agents.yaml → unit-test-agents",
    "loop-unit-real": "pytest tests/unit on LIVE Ollama (no mocks) via agents.yaml → unit-test-agents",
    "loop-e2e": "3 standing e2e gates (ticket20 / ticket22 / greetings) via agents.yaml → integration-test-agents",
    "loop-build-app": "docker compose tools.yaml run app: npm run build (rollup)",
    "loop-test-app": "docker compose tools.yaml run app: npm test (jest)",
    "loop-secret-scan-tests": "secret-scanner pytest suite (real gitleaks, no mocks) containerized via docker-compose-files/gitleaks-tests.yaml (fail-closed)",
    "check-docs-sync": "scripts/check_docs_sync.py — FAIL if any B8 source-of-truth doc drifts (stage order / loop-ts-floor / B-range B1–B32) — FINAL gate",
}


def ensure_repo_root() -> str:
    """Find the repo root by walking upward from cwd looking for openspec/changes."""
    here = os.getcwd()
    while here != "/":
        marker = os.path.join(here, "openspec", "changes")
        if os.path.isdir(marker):
            return here
        here = os.path.dirname(here)
    # Fallback to git rev-parse
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, check=False,
        ).stdout.strip()
        if out:
            return out
    except Exception:
        pass
    return os.getcwd()


def run_stage_with_make(repo_root: str, stage: str, timeout_s: int) -> tuple[str, int]:
    """Run a Makefile target for this stage. Returns (status, exit_code).

    Status is one of: PASS, FAIL, TIMEOUT
    """
    desc = STAGE_DESC.get(stage, f"make {stage}")
    start_ts = datetime.datetime.now().strftime("%H:%M:%S")
    start_epoch = time.time()

    log_path = f"/tmp/loop_{stage}.log"

    print(f"=== {stage} (timeout {timeout_s}s) ===", flush=True)
    print(f"    [{start_ts}] → {desc}", flush=True)
    print(f"    --- live output below (also saved to {log_path}) ---", flush=True)

    cmd = ["make", stage]

    # Determine if we need PTY synthesis for nerdctl containers.
    # nerdctl compose run HARDCODES --interactive --tty, so the container needs a real console.
    use_pty = _has_nerdctl()

    log_fp = open(log_path, "w", encoding="utf-8")

    try:
        # Run make with PTY synthesis using our nerdctl_pty.py runner
        env = os.environ.copy()
        # Ensure OLLAMA_HOST is set for stages that need live Ollama (e2e, unit-real).
        # Default is platform-aware to match the Makefile: Linux -> 127.0.0.1:11434,
        # macOS/colima -> host.lima.internal:11434 (127.0.0.1 is Connection-refused there).
        if "OLLAMA_HOST" not in env:
            if sys.platform == "darwin":
                env["OLLAMA_HOST"] = "http://host.lima.internal:11434"
            else:
                env["OLLAMA_HOST"] = "http://127.0.0.1:11434"
        if use_pty:
            # Use our Python PTY runner for proper pseudo-terminal support
            import tempfile
            cmd_file = tempfile.mktemp(suffix=".cmd")
            with open(cmd_file, "w") as f:
                f.write(" ".join(cmd))
            process = subprocess.Popen(
                ["python3", "scripts/nerdctl_pty.py", "--file", cmd_file],
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=repo_root,
                env=env,
            )
        else:
            # Fallback: run make directly (works if no PTY needed)
            process = subprocess.Popen(
                cmd,
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=repo_root,
                env=env,
            )

        # Stream live output from log file to terminal and track elapsed time.
        last_log_size = 0
        heartbeat_interval = 15  # seconds
        last_heartbeat_time = time.time()

        while True:
            now_epoch = time.time()
            elapsed = int(now_epoch - start_epoch)

            if elapsed > timeout_s:
                # Timeout — kill the process tree.
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)

                end_ts = datetime.datetime.now().strftime("%H:%M:%S")
                log_fp.flush()
                log_fp.close()
                print(f"\n  → TIMEOUT (exceeded {timeout_s}s; see {log_path})", flush=True)
                print(f"    [{end_ts}] elapsed {elapsed}s", flush=True)
                return ("TIMEOUT", 124)

            # Stream any new lines from the log to terminal
            try:
                log_size = os.path.getsize(log_path)
            except OSError:
                log_size = last_log_size

            if log_size > last_log_size:
                log_fp.flush()
                with open(log_path, "r", encoding="utf-8", errors="replace") as lf:
                    lf.seek(last_log_size)
                    for line in lf:
                        print(line, end="", flush=True)
                last_log_size = log_size

            # Heartbeat if the stage has been quiet for a while.
            if (time.time() - last_heartbeat_time) >= heartbeat_interval:
                last_heartbeat_time = time.time()
                print(f"    ... {elapsed}s elapsed (stage quiet, still running)", flush=True)

            time.sleep(2.5)

    except Exception as exc:
        end_ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n  → FAIL ({exc})", flush=True)
        print(f"    [{end_ts}] elapsed {int(time.time() - start_epoch)}s", flush=True)
        log_fp.flush()
        log_fp.close()
        return ("FAIL", 1)

    # Wait for process completion.
    process.wait()
    rc = process.returncode

    end_ts = datetime.datetime.now().strftime("%H:%M:%S")
    elapsed = int(time.time() - start_epoch)
    log_fp.flush()
    log_fp.close()

    try:
        log_fp.close()
    except Exception:
        pass

    if rc != 0:
        print(f"\n  → FAIL (rc={rc}; see {log_path})", flush=True)
        print(f"    [{end_ts}] elapsed {elapsed}s", flush=True)
        return ("FAIL", rc)

    print(f"\n  → PASS", flush=True)
    print(f"    [{end_ts}] elapsed {elapsed}s", flush=True)
    return ("PASS", rc)


def _has_nerdctl() -> bool:
    """Check if nerdctl is available in PATH."""
    try:
        rc = subprocess.run(
            "nerdctl version", shell=True, capture_output=True, timeout=10, check=False
        ).returncode
        return rc == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _has_command(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        return subprocess.run(
            f"which {cmd}", shell=True, capture_output=True, timeout=5, check=False
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_preflight_checks(repo_root: str) -> int:
    """Run the B8 doc-sync pre-flight checks before any loop stages."""
    print("=== PRE-FLIGHT 0: check-docs-sync unit tests + live gate ===", flush=True)
    overall = 0

    rc = subprocess.run(
        ["make", "test-check-docs-sync"],
        cwd=repo_root, timeout=180,
        stdout=sys.stdout, stderr=subprocess.STDOUT,
    ).returncode
    if rc != 0:
        print("  → PRE-FLIGHT 0 FAIL: check-docs-sync unit tests failed (gate logic broken)", flush=True)
        overall = 1

    rc = subprocess.run(
        ["make", "check-docs-sync"],
        cwd=repo_root, timeout=120,
        stdout=sys.stdout, stderr=subprocess.STDOUT,
    ).returncode
    if rc != 0:
        print("  → PRE-FLIGHT 0 FAIL: B8 doc/loop sync drift detected", flush=True)
        overall = 1

    if overall != 0:
        print("RESULT: FAILURE — pre-flight B8 doc-sync gate is red. Fix before running stages.", flush=True)
        return 1

    print("  → PRE-FLIGHT 0 PASS", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="run_loop_harness",
        description="Run the loop-harness gate (AGENTS.md behaviour B20). Runs all stages in order and prints per-stage results.",
    )
    parser.add_argument(
        "--hermetic",
        action="store_true",
        help="Run only hermetic stages: loop-collect, loop-ts-floor, loop-unit",
    )
    args = parser.parse_args()

    repo_root = ensure_repo_root()

    # Pre-flight 0
    if run_preflight_checks(repo_root) != 0:
        return 1

    summary: list[tuple[str, str]] = []
    overall = 0

    for stage in STAGES:
        is_hermetic = stage in HERMETIC_STAGES

        if args.hermetic and not is_hermetic:
            print(f"=== {stage} ===", flush=True)
            print("  → SKIP (--hermetic mode; run full script for this stage)", flush=True)
            summary.append((stage, "SKIP"))
            continue

        cap = STAGE_TIMEOUT.get(stage, 600)
        status, _rc = run_stage_with_make(repo_root, stage, cap)

        if status in ("FAIL", "TIMEOUT"):
            overall = 1

        summary.append((stage, status))

    # Print summary
    print("\n================ LOOP-HARNESS SUMMARY ================", flush=True)
    for name, status in summary:
        pad = max(0, 20 - len(name))
        print(f"  {name}{' ' * pad} {status}", flush=True)
    print("=======================================================", flush=True)

    if overall == 0:
        print("RESULT: ALL RUN STAGES GREEN.", flush=True)
    else:
        print("RESULT: FAILURE/TIMEOUT — a gate is red. Fix root cause and re-run.", flush=True)

    return overall


if __name__ == "__main__":
    raise SystemExit(main())
