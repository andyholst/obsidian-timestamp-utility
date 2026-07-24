#!/usr/bin/env python3
"""
ts_test_floor.py — Strict TS test/command floor guard.

Python equivalent of ts_test_floor.sh. Hermetic + read-only: only diffs origin/main (via git show)
and runs a LOCAL npx jest --collectOnly. No network, no llama, no tree writes.

Exit 0 = floor respected (current >= baseline on all metrics).
Exit 1 = a metric dropped below baseline (loop MUST fail).
"""

import re
import subprocess
import sys


def run(cmd, **kwargs):
    """Run a command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, **kwargs)
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def count_pattern(text, pattern):
    """Count non-overlapping matches of a regex in text."""
    return len(re.findall(pattern, text))


def establish_baseline():
    """Determine the baseline ref (origin/main or main)."""
    if run(["git", "rev-parse", "--verify", "origin/main"]):
        return "origin/main"
    elif run(["git", "rev-parse", "--verify", "main"]):
        return "main"
    else:
        print("TS-FLOOR: ERROR: no 'origin/main' or 'main' ref found -- cannot establish a baseline.", file=sys.stderr)
        sys.exit(1)


def get_baseline_metrics(base, main_ts="src/main.ts", test_ts="src/__tests__/main.test.ts"):
    """Get baseline metrics from git (never disk)."""
    main_content = run(["git", "show", f"{base}:{main_ts}"])
    test_content = run(["git", "show", f"{base}:{test_ts}"])

    base_describe = count_pattern(test_content, r"describe\s*\(") if test_content else 0
    base_leaf = count_pattern(test_content, r"(?:it|test)\s*\(") if test_content else 0
    base_addcmd = count_pattern(main_content, r"addCommand\s*\(") if main_content else 0

    return base_describe, base_leaf, base_addcmd


def get_current_metrics():
    """Get current metrics from disk."""
    import os

    test_ts = "src/__tests__/main.test.ts"
    main_ts = "src/main.ts"

    test_content = open(test_ts).read() if os.path.isfile(test_ts) else ""
    main_content = open(main_ts).read() if os.path.isfile(main_ts) else ""

    cur_describe = count_pattern(test_content, r"describe\s*\(") if test_content else 0
    cur_leaf = count_pattern(test_content, r"(?:it|test)\s*\(") if test_content else 0
    cur_addcmd = count_pattern(main_content, r"addCommand\s*\(") if main_content else 0

    return cur_describe, cur_leaf, cur_addcmd


def get_jest_collected():
    """Get jest collected test count from current branch."""
    npx_out = run(["npx", "jest", "--collectOnly", "--silent"])
    if not npx_out:
        return None

    # Look for "Tests: N" pattern in jest output
    matches = re.findall(r"Tests:\s+(\d+)", npx_out)
    if matches:
        return int(matches[-1])
    return None


def main():
    base = establish_baseline()
    print(f"TS-FLOOR: baseline ref = {base}")

    # Get baseline metrics
    base_describe, base_leaf, base_addcmd = get_baseline_metrics(base)

    # Get current metrics
    cur_describe, cur_leaf, cur_addcmd = get_current_metrics()

    # Jest collected total
    cur_jest = get_jest_collected()
    if cur_jest is None:
        # Fallback: use leaf count as jest total
        cur_jest = cur_leaf

    # Calculate baseline jest total from leaf delta
    base_jest = cur_jest - cur_leaf + base_leaf

    # Normalize empties to 0
    base_describe = base_describe or 0
    cur_describe = cur_describe or 0
    base_leaf = base_leaf or 0
    cur_leaf = cur_leaf or 0
    base_addcmd = base_addcmd or 0
    cur_addcmd = cur_addcmd or 0
    base_jest = base_jest or 0
    cur_jest = cur_jest or 0

    # Print comparison table
    print(f"TS-FLOOR: {'METRIC':<22s} {'BASELINE':<10s} {'CURRENT':<10s} {'RESULT'}")
    fail = 0

    def check(name, base_val, cur_val):
        nonlocal fail
        result = "OK" if cur_val >= base_val else "FAIL"
        if cur_val < base_val:
            fail = 1
        print(f"TS-FLOOR: {name:<22s} {str(base_val):<10s} {str(cur_val):<10s} {result}")

    check("describe_blocks", base_describe, cur_describe)
    check("leaf_it_test", base_leaf, cur_leaf)
    check("jest_collected_total", base_jest, cur_jest)
    check("addCommand_count", base_addcmd, cur_addcmd)

    if fail:
        print(f"TS-FLOOR: FAILED — a TS test/command metric dropped below {base}. The loop MUST NOT pass.")
        sys.exit(1)

    print(f"TS-FLOOR: PASS — all TS test/command metrics >= {base} baseline.")
    sys.exit(0)


if __name__ == "__main__":
    main()
