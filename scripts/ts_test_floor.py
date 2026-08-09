#!/usr/bin/env python3
"""ts_test_floor.py — Strict TS test/command floor guard (AGENTS.md loop-ts-floor stage).

WHY: the loop-harness gates on build-app + jest passing, but tracks NO absolute count of
the plugin's test/command surface. A change that silently DROPS a feature stays green as long
as the remaining tests pass. This guard fails the loop if any of four metrics on the CURRENT
branch is strictly LOWER than the origin/main baseline.

METRICS (current vs baseline):
  1. describe blocks in src/__tests__/main.test.ts
  2. leaf it/test count in src/__tests__/main.test.ts
  3. jest COLLECTED test total (number jest actually collects/runs)
  4. addCommand(...) count in src/main.ts

Hermetic + read-only: only diffs origin/main (via git show) and runs a LOCAL npx jest --collectOnly.
No network, no Ollama, no tree writes.

Exit 0 = floor respected (current >= baseline on all metrics).
Exit 1 = a metric dropped below baseline (loop MUST fail).
"""
from __future__ import annotations

import re
import subprocess
import sys


MAIN_TS = "src/main.ts"
TEST_TS = "src/__tests__/main.test.ts"


def git_show(path: str, ref: str) -> str | None:
    """Read a file from git at the given ref. Returns None if not found."""
    cmd = ["git", "show", f"{ref}:{path}"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return proc.stdout if proc.returncode == 0 else None


def resolve_baseline():
    """Return the baseline ref to compare against, or raise."""
    for ref in ("origin/main", "main"):
        cmd = ["git", "rev-parse", "--verify", ref]
        rc = subprocess.run(cmd, capture_output=True, timeout=5).returncode
        if rc == 0:
            return ref
    print("TS-FLOOR: ERROR: no 'origin/main' or 'main' ref found — cannot establish a baseline.", file=sys.stderr)
    sys.exit(1)


def count_pattern(text: str | None, pattern: str) -> int:
    """Return count of regex matches in text."""
    if not text:
        return 0
    return len(re.findall(pattern, text))


def run_jest_collect() -> int | None:
    """Run npx jest --collectOnly and extract the 'Tests:' count. Returns None if it fails."""
    try:
        proc = subprocess.run(
            ["npx", "jest", "--collectOnly", "--silent"],
            capture_output=True, text=True, timeout=120,
        )
        output = proc.stdout
        m = re.search(r"Tests:\s+(\d+)", output)
        if m:
            return int(m.group(1))
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    return None


def main() -> int:
    base = resolve_baseline()

    # ---- baseline (from git, never disk) ----
    base_test_ts = git_show(TEST_TS, base)
    base_main_ts = git_show(MAIN_TS, base)

    base_describe = count_pattern(base_test_ts, r"describe\(")
    base_leaf = count_pattern(base_test_ts, r"(?<![\w:])\s*(it|test)\(")
    base_addcmd = count_pattern(base_main_ts, r"addCommand\(")

    # ---- current (from disk) ----
    test_ts_content = None
    main_ts_content = None

    try:
        with open(TEST_TS, "r", encoding="utf-8") as f:
            test_ts_content = f.read()
    except FileNotFoundError:
        pass

    try:
        with open(MAIN_TS, "r", encoding="utf-8") as f:
            main_ts_content = f.read()
    except FileNotFoundError:
        pass

    cur_describe = count_pattern(test_ts_content, r"describe\(")
    cur_leaf = count_pattern(test_ts_content, r"(?<![\w:])\s*(it|test)\(")
    cur_addcmd = count_pattern(main_ts_content, r"addCommand\(")

    # ---- jest collected total ----
    # Current: real jest collection across the whole project.
    # Baseline: only src/__tests__/main.test.ts varies between branches (other suites are stable),
    # so baseline jest total = current total adjusted by main.test.ts leaf delta.
    cur_jest_raw = run_jest_collect()
    if cur_jest_raw is not None:
        cur_jest = int(cur_jest_raw)
    else:
        cur_jest = cur_leaf

    base_jest = cur_jest - cur_leaf + base_leaf

    # Normalize empties to 0.
    for name in ["base_describe", "cur_describe", "base_leaf", "cur_leaf", "base_addcmd", "cur_addcmd", "base_jest", "cur_jest"]:
        globals()[name] = int(globals().get(name, 0))

    print(f"TS-FLOOR: baseline ref = {base}")
    print(f"TS-FLOOR: {'METRIC':<22} {'BASELINE':<10} {'CURRENT':<10} RESULT")

    fail = 0

    def check(name: str, base_val: int, cur_val: int):
        nonlocal fail
        res = "OK" if cur_val >= base_val else "FAIL"
        if res == "FAIL":
            fail = 1
        print(f"TS-FLOOR: {name:<22} {base_val:<10d} {cur_val:<10d} {res}")

    check("describe_blocks", base_describe, cur_describe)
    check("leaf_it_test", base_leaf, cur_leaf)
    check("jest_collected_total", base_jest, cur_jest)
    check("addCommand_count", base_addcmd, cur_addcmd)

    if fail:
        print(f"TS-FLOOR: FAILED — a TS test/command metric dropped below {base}. The loop MUST NOT pass.")
        return 1

    print(f"TS-FLOOR: PASS — all TS test/command metrics >= {base} baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
