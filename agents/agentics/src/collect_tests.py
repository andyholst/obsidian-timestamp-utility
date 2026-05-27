#!/usr/bin/env python3

import argparse
import subprocess
import sys
import os
import re


def main():
    parser = argparse.ArgumentParser(
        description="Collect test names using pytest --collect-only"
    )
    parser.add_argument("type", choices=["unit", "unit-mock", "integration"])
    args = parser.parse_args()

    if args.type in ["unit", "unit-mock"]:
        test_dir = "tests/unit"
    else:
        test_dir = "tests/integration"

    # Run pytest tests/integration/ --collect-only -vv (override -q from config)
    cmd = ["python", "-m", "pytest", f"{test_dir}/", "--collect-only", "-vv"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd="/app")

    if result.returncode not in (0, 5):
        print(
            f"Pytest collection error (exit code {result.returncode}):", file=sys.stderr
        )
        print("STDOUT preview:", file=sys.stderr)
        for line in result.stdout.splitlines()[:20]:
            print(repr(line), file=sys.stderr)
        if result.stderr.strip():
            print("STDERR:", result.stderr, file=sys.stderr)
        sys.exit(1)

    tests = []
    stack = []
    in_collection = False
    clean_name_re = re.compile(r"\s*\([^)]*\)\s*$")
    for line in result.stdout.splitlines():
        line = line.rstrip()
        if "collected " in line and "items" in line:
            in_collection = True
            continue
        if not in_collection or not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        while len(stack) > (indent // 2):
            stack.pop()
        stripped = line.lstrip(" ")
        m = re.match(r"<(Module|Class|Function|Coroutine)\s+([^>]+)>", stripped)
        if m:
            kind, raw_name = m.groups()
            name = clean_name_re.sub("", raw_name).strip()
            if kind in ("Module", "Class"):
                stack.append(name)
            elif kind in ("Function", "Coroutine") and name.startswith("test_"):
                full_path = "::".join(stack + [name])
                tests.append(full_path)
    if not tests:
        print("DEBUG: No tests. STDOUT preview:", file=sys.stderr)
        for l in result.stdout.splitlines()[:20]:
            print(repr(l.strip()), file=sys.stderr)
        print("No tests found in collection output", file=sys.stderr)
        sys.exit(1)

    output_file = f"collected_tests_{args.type}.txt"
    with open(output_file, "w") as f:
        f.write("\n".join(tests) + "\n")

    print(f"Collected {len(tests)} tests to {output_file}")
    if len(tests) < 100:
        print("DEBUG FULL PYTEST OUTPUT:")
        print(result.stdout)


if __name__ == "__main__":
    main()
