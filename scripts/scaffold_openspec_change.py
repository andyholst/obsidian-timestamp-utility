#!/usr/bin/env python3
"""scaffold_openspec_change.py — reproducible harness for creating OpenSpec changes.

Wraps the REAL openspec CLI (durable behaviour B15: the change directory is produced by
`openspec new change`, NEVER hand-written by this script), then seeds the conventional
proposal.md / tasks.md / specs/<CAPABILITY>/spec.md from a template so every new
change has the same validated shape. Finally runs `openspec validate` so the change is
green before any implementation work begins.

No git commit/push is performed (B4/B14) — only openspec/changes/<name>/ is written.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import textwrap


def kebab_to_title(name: str) -> str:
    """my-cool-change → 'My Cool Change'."""
    return " ".join(part.capitalize() for part in name.split("-"))


def ensure_openspec_cli() -> str | None:
    """Return path to openspec CLI or None if not found."""
    # Try system PATH first
    cli = shutil.which("openspec")
    if cli is None:
        # Try node_modules/.bin (works for non-scoped packages)
        cli = os.path.join(os.getcwd(), "node_modules", ".bin", "openspec")
        if os.path.isfile(cli):
            return cli
    # Fallback: use npx for scoped packages like @fission-ai/openspec
    return "npx"


def run_openspec(*args: str, reason: str | None = None) -> int:
    """Run openspec CLI via subprocess, return exit code."""
    cli = ensure_openspec_cli()
    if cli == "npx":
        cmd = ["npx", "@fission-ai/openspec"] + list(args)
    else:
        cmd = [cli] + list(args)
    print(f"[scaffold] running: {' '.join(cmd)}")
    rc = subprocess.run(cmd).returncode
    if rc != 0 and reason:
        print(f"ERROR: '{reason}' failed." if reason else f"ERROR: {' '.join(cmd)} failed.", file=sys.stderr)
        return rc
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="scaffold_openspec_change",
        description="Reproducible harness to create an OpenSpec change via the real openspec CLI (B15).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        EXAMPLES
          scripts/scaffold_openspec_change.py --name add-dark-mode-toggle
          scripts/scaffold_openspec_change.py --name add-dark-mode-toggle --capability dark-mode --desc "Toggle theme" --goal "Users switch themes"
        """),
    )
    parser.add_argument("--name", required=True, help="Kebab-case change name (REQUIRED)")
    parser.add_argument("--desc", default="", help="One-line description for the change README.md")
    parser.add_argument("--goal", default="", help="Goal metadata for .openspec.yaml")
    parser.add_argument("--capability", default="", help="Capability name for specs/<cap>/spec.md (defaults to --name)")

    args = parser.parse_args()
    name = args.name.strip()
    capability = args.capability.strip() or name
    desc = args.desc.strip()
    goal = args.goal.strip()

    if not name:
        print("ERROR: --name is required.", file=sys.stderr)
        return 1

    change_dir = os.path.join(os.getcwd(), "openspec", "changes", name)
    if os.path.isdir(change_dir):
        print(f"ERROR: {change_dir} already exists — refusing to overwrite an existing change.", file=sys.stderr)
        return 1

    title_line = kebab_to_title(name)

    # STEP 1: invoke the real openspec CLI (B15)
    cli_args = ["new", "change", name]
    if desc:
        cli_args.extend(["--description", desc])
    if goal:
        cli_args.extend(["--goal", goal])
    rc = run_openspec(*cli_args, reason=f"openspec new change {name}")
    if rc != 0:
        return rc

    # Sanity check: the CLI must have created .openspec.yaml
    openspec_yaml = os.path.join(change_dir, ".openspec.yaml")
    if not os.path.isfile(openspec_yaml):
        print(f"ERROR: CLI did not produce {openspec_yaml} — aborting.", file=sys.stderr)
        return 1

    # STEP 2: seed files from template
    spec_dir = os.path.join(change_dir, "specs", capability)
    os.makedirs(spec_dir, exist_ok=True)
    print(f"[scaffold] seeding proposal.md / tasks.md / specs/{capability}/spec.md from template...")

    proposal_md = f"""\
# Proposal: {title_line}

## Why
{desc or title_line}
TODO: explain the motivation for this change — what problem it solves and why now.

## What Changes
TODO: describe the concrete changes (files, behaviours, commands). Keep it factual.

## Capabilities
- `{capability}` (new): TODO: one-line description of the capability this change introduces.

## Impact
TODO: call out side effects, dependencies, and what MUST NOT regress (loop-harness gates,
deterministic floor, no git commit/push — B4/B14).
"""
    tasks_md = f"""\
# Tasks

- [ ] 1.1 Implement the core change for `{name}` (TODO: concrete, verifiable step)
- [ ] 2.1 Verify: run the relevant gate(s) — e.g. `make build-app` / `make test-app` / `make loop-unit`
- [ ] 2.2 TODO: add/adjust tests that prove the behaviour
- [ ] 3.1 B8-sync: update AGENTS.md + openspec-loop-harness skill if behaviour/docs changed
- [ ] 4.1 `openspec validate {name}` passes
"""
    spec_md = f"""\
# {capability} Specification

## ADDED Requirements

### Requirement: TODO — name the requirement
The system MUST <describe the required behaviour in imperative form>.

#### Scenario: TODO — name the scenario
- **WHEN** <condition or action>
- **THEN** <expected outcome>
"""
    with open(os.path.join(change_dir, "proposal.md"), "w", encoding="utf-8") as f:
        f.write(proposal_md)
    with open(os.path.join(change_dir, "tasks.md"), "w", encoding="utf-8") as f:
        f.write(tasks_md)
    with open(os.path.join(spec_dir, "spec.md"), "w", encoding="utf-8") as f:
        f.write(spec_md)

    # STEP 3: validate the change (openspec validate <name>)
    print(f"[scaffold] running 'openspec validate {name}'…")
    rc = run_openspec("validate", name, reason=f"openspec validate {name}")
    if rc != 0:
        print(f"ERROR: 'openspec validate {name}' failed — review the seeded files.", file=sys.stderr)
        return rc

    print(f"[scaffold] OK: change '{name}' created and validated at {change_dir}")
    print(f"[scaffold] next: edit proposal.md / tasks.md / specs/{capability}/spec.md, then implement + verify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
