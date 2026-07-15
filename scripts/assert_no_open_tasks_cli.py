#!/usr/bin/env python3
"""Container entrypoint: assert an OpenSpec change has no open tasks (B16 gate).

Imported as a CLI so phase7-archive can call it without nested shell quoting.
Usage: python3 /project/scripts/assert_no_open_tasks_cli.py <change-name>
Exits non-zero (and raises) if the change has any open `- [ ]` tasks.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path("/project").resolve()
sys.path.insert(0, str(REPO_ROOT / "agents" / "agentics" / "src"))


def main() -> int:
    if len(sys.argv) < 2:
        print("ERROR: usage: assert_no_open_tasks_cli.py <change-name>", file=sys.stderr)
        return 2
    change = sys.argv[1]
    try:
        from openspec_loader import assert_no_open_tasks
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: cannot import openspec_loader: {exc}", file=sys.stderr)
        return 3
    try:
        assert_no_open_tasks(change)
    except Exception as exc:  # assert_no_open_tasks raises RuntimeError on open tasks
        print(f"FAIL(B16): {exc}", file=sys.stderr)
        return 1
    print(f"OK: no open tasks in {change}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
