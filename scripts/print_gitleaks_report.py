#!/usr/bin/env python3
"""Print gitleaks JSON findings as 'file | rule | line' (redacted-friendly).

Reads the report at the path given as argv[1]; exits 0. Used by the
`loop-secret-scan` Makefile target so the operator can SEE which file/rule fired.
"""
import json
import sys


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else ".gitleaks-report.json"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            rows = json.load(fh)
    except Exception:
        rows = []
    if not rows:
        return 0
    for f in rows:
        print("  - %s | %s | line %s" % (
            f.get("File", "?"),
            f.get("RuleID", "?"),
            f.get("StartLine", "?"),
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
