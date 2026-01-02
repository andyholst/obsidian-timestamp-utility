#!/usr/bin/env python3

import argparse
import re
import sys
import os

TYPES = {'unit', 'unit-mock', 'integration'}

def main():
    parser = argparse.ArgumentParser(description="Parse executed tests from pytest output")
    parser.add_argument("type")
    args = parser.parse_args()

    if args.type not in TYPES:
        print(f"Invalid type: {args.type}. Must be one of {TYPES}", file=sys.stderr)
        sys.exit(1)

    input_file = f"/project/executed_tests_{args.type}.txt"
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    with open(input_file, "r") as f:
        content = f.read()

    collected_file = f"/project/collected_tests_{args.type}.txt"
    if not os.path.exists(collected_file):
        print(f"Collected file not found: {collected_file}", file=sys.stderr)
        sys.exit(1)

    with open(collected_file, "r") as f:
        collected_tests = [line.strip() for line in f if line.strip()]
    expected_count = len(collected_tests)

    passed_match = re.search(r'(\d+) passed', content)
    if passed_match and int(passed_match.group(1)) == expected_count:
        output_file = f"/project/executed_list_{args.type}.txt"
        with open(output_file, "w") as f:
            for test in collected_tests:
                f.write(test + "\n")
        print(f"Copied {expected_count} passed tests from collected to {output_file}")
    else:
        output_file = f"/project/executed_list_{args.type}.txt"
        with open(output_file, "w") as f:
            pass  # empty file
        passed_count = int(passed_match.group(1)) if passed_match else 0
        print(f"Not all tests passed ({passed_count}/{expected_count}). Left {output_file} empty.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()