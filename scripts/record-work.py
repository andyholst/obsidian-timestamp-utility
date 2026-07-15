#!/usr/bin/env python3
"""record-work.py — scriptable OpenSpec-change → agent-wiki work-log entry.

Replaces the never-created `record-work` skill that AGENTS.md Phase 7 references.
Collects the context for a work-log entry (change proposal/tasks/specs, openspec
status + validate, git branch + recent commit) and asks the project-manager Hermes
CLI (`hermes -z`) to draft the prose, then writes:

    agent-wiki/YYYY-MM-DD-<change>.md
    agent-wiki/index.md           (appends a line under "## Change Entries")

Usage:
    python3 scripts/record-work.py --change <name> [--date YYYY-MM-DD] [--wiki-dir agent-wiki] [--dry-run]

No git commit/push is performed (B4/B14): only agent-wiki/ files are written.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR_DEFAULT = REPO_ROOT / "agent-wiki"


def log(msg: str) -> None:
    print(f"[record-work] {msg}", flush=True)


def run(cmd: list[str], capture: bool = True) -> str:
    """Run a command; return stdout (or '' on failure). Best-effort for non-critical gathers."""
    try:
        res = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=capture,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log(f"warn: {'timeout' if isinstance(exc, subprocess.TimeoutExpired) else 'missing'} running {cmd}: {exc}")
        return ""
    if res.returncode != 0:
        log(f"warn: {' '.join(cmd)} exited {res.returncode}")
    return (res.stdout or "").strip()


def read_change_text(change_dir: Path) -> str:
    """Concatenate proposal.md + tasks.md + every spec.md under specs/ for the prompt."""
    parts: list[str] = []
    for name in ("proposal.md", "tasks.md"):
        p = change_dir / name
        if p.is_file():
            parts.append(f"# {name}\n{p.read_text(encoding='utf-8')}")
    specs_dir = change_dir / "specs"
    if specs_dir.is_dir():
        for spec_file in sorted(specs_dir.rglob("spec.md")):
            parts.append(f"# {spec_file.relative_to(change_dir)}\n{spec_file.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def collect_context(change: str) -> dict:
    change_dir = REPO_ROOT / "openspec" / "changes" / change
    if not change_dir.is_dir():
        log(f"ERROR: openspec/changes/{change} not found")
        sys.exit(1)

    return {
        "change": change,
        "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "(unknown)",
        "recent_commit": run(["git", "log", "-1", "--pretty=%h %s"]) or "(none)",
        "openspec_status": run(["openspec", "status", "--change", change]),
        "openspec_validate": run(["openspec", "validate", change]) or "(validate produced no output)",
        "change_text": read_change_text(change_dir),
    }


def draft_prose(ctx: dict) -> str:
    """Ask the project-manager Hermes CLI to draft the entry prose (Summary,
    Verification Against Spec, Key Decisions, Current Status, Recommended Next Steps).
    Falls back to a deterministic stub if hermes -z returns nothing."""
    prompt = f"""You are writing ONE work-log entry for the obsidian-timestamp-utility project's
agent-wiki, recording the completion of an OpenSpec change. Write only the BODY of the entry
(no top-level title, no code fences). Use these Markdown sections in order:

## Summary
(2-4 sentences: what the change did and why)

## Verification Against Spec
(For each Requirement in the change's spec, one line: "- Requirement \"<name>\": <how verified> ✅/⚠️".
Base this on the openspec validate + status output and the change text below.)

## Key Decisions
(Bulleted: non-obvious choices made, pitfalls avoided)

## Current Status
(One sentence: complete / in-progress / blocked)

## Recommended Next Steps
(Bulleted, or "None — archive." if done)

Ground everything in the provided context. Be specific and file-grounded, not meta.
Never commit or push (B4/B14) — do not mention committing.

CONTEXT
Change: {ctx['change']}
Branch: {ctx['branch']}
Recent commit: {ctx['recent_commit']}
openspec validate: {ctx['openspec_validate']}
openspec status:
{ctx['openspec_status']}

Change artifact text (proposal/tasks/specs):
{ctx['change_text']}
"""
    log("invoking `hermes -z` (profile project-manager) to draft prose...")
    try:
        res = subprocess.run(
            ["hermes", "profile", "use", "project-manager"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if res.returncode != 0:
            log(f"warn: 'hermes profile use project-manager' exited {res.returncode}")
        out = subprocess.run(
            ["hermes", "-z", prompt],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log(f"warn: hermes invocation failed ({exc}); using stub body")
        return ""
    if out.returncode != 0:
        log(f"warn: hermes -z exited {out.returncode}; using stub body")
        return ""
    body = (out.stdout or "").strip()
    return body


def stub_body(ctx: dict) -> str:
    return (
        "## Summary\n"
        f"OpenSpec change `{ctx['change']}` completed on branch `{ctx['branch']}`. "
        "Prose drafting via the Hermes CLI was unavailable; this is a deterministic stub entry.\n\n"
        "## Verification Against Spec\n"
        f"- `openspec validate {ctx['change']}` output:\n```\n{ctx['openspec_validate']}\n```\n\n"
        "## Key Decisions\n"
        "- Scriptable `record-work` tooling written (scripts/record-work.py + Makefile `record-work`).\n\n"
        "## Current Status\n"
        "Complete (auto-generated stub — re-run with a reachable Hermes CLI for full prose).\n\n"
        "## Recommended Next Steps\n"
        "None — archive.\n"
    )


def write_entry(wiki_dir: Path, change: str, day: str, ctx: dict, prose: str) -> Path:
    wiki_dir.mkdir(parents=True, exist_ok=True)
    entry_path = wiki_dir / f"{day}-{change}.md"
    body = prose or stub_body(ctx)
    content = (
        f"# {change} — Work Log\n\n"
        f"**Date:** {day}\n"
        f"**OpenSpec Change:** `{change}`\n"
        f"**Branch:** `{ctx['branch']}`\n\n"
        f"{body}\n"
    )
    entry_path.write_text(content, encoding="utf-8")
    log(f"wrote {entry_path.relative_to(REPO_ROOT)}")
    return entry_path


def update_index(wiki_dir: Path, change: str, day: str, entry_rel: str, summary_line: str) -> None:
    index_path = wiki_dir / "index.md"
    if not index_path.is_file():
        index_path.write_text(
            "# Agent Wiki Index\n\n"
            "This wiki documents work done on OpenSpec changes for the **obsidian-timestamp-utility** project.\n\n"
            "## How this wiki is maintained\n\n"
            "- One entry per completed OpenSpec change, written by `scripts/record-work.py` (run via "
            "`make record-work CHANGE=<name>`).\n"
            "- Entries follow the naming convention: `YYYY-MM-DD-<change-folder-name>.md`.\n"
            "- Weekly summaries live in `weekly-summaries/`.\n\n"
            "## Change Entries\n\n",
            encoding="utf-8",
        )
    text = index_path.read_text(encoding="utf-8")
    line = f"- [{day}-{change}]({entry_rel}) — {summary_line}"
    # Avoid duplicate lines for the same change.
    if f"{day}-{change}]({entry_rel})" in text:
        log(f"index already links {day}-{change}; skipping append")
        return
    if "## Change Entries" in text:
        text = text.replace("## Change Entries\n", f"## Change Entries\n{line}\n", 1)
    else:
        text = text.rstrip() + f"\n\n## Change Entries\n\n{line}\n"
    index_path.write_text(text, encoding="utf-8")
    log(f"updated {index_path.relative_to(REPO_ROOT)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate an agent-wiki work-log entry for an OpenSpec change.")
    ap.add_argument("--change", required=True, help="OpenSpec change name (openspec/changes/<name>)")
    ap.add_argument("--date", default=date.today().isoformat(), help="Entry date YYYY-MM-DD (default: today)")
    ap.add_argument("--wiki-dir", default=str(WIKI_DIR_DEFAULT), help="agent-wiki directory")
    ap.add_argument("--dry-run", action="store_true", help="Print what would be written; do not write files")
    args = ap.parse_args()

    wiki_dir = Path(args.wiki_dir).resolve()
    ctx = collect_context(args.change)
    prose = draft_prose(ctx)

    # A short one-line summary for index.md: the first real prose line (skip blank lines and
    # markdown section headers like "## Summary"), else a deterministic fallback.
    first_line = ""
    for l in (prose or "").splitlines():
        s = l.strip().lstrip("#").strip("- ").strip()
        if s and not s.startswith("#"):
            first_line = s
            break
    summary_line = (first_line[:160] if first_line else f"work-log entry for `{args.change}`")

    if args.dry_run:
        log(f"DRY-RUN: would write {wiki_dir / f'{args.date}-{args.change}.md'}")
        log(f"DRY-RUN: would append to index.md: - [{args.date}-{args.change}] — {summary_line}")
        return 0

    entry = write_entry(wiki_dir, args.change, args.date, ctx, prose)
    update_index(wiki_dir, args.change, args.date, entry.name, summary_line)
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
