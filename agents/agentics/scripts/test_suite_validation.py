#!/usr/bin/env python3
"""Test suite validation script - validates the agentics test suite structure and coverage."""

import subprocess
import sys
import os

def main():
    os.chdir("/app")

    # Run unit tests with coverage
    print("=== Running unit tests with coverage ===")
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/unit/", "-q", "--tb=short",
         "--cov=src", "--cov-report=term-missing", "--cov-fail-under=50"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"Unit tests failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

    # Run integration tests (collect only to verify they're importable)
    print("=== Collecting integration tests ===")
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/integration/", "--collect-only", "-q"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode not in (0, 5):  # 5 = no tests collected
        print(f"Integration test collection failed", file=sys.stderr)
        sys.exit(result.returncode)

    print("=== Test suite validation passed ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
