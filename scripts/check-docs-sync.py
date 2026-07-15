#!/usr/bin/env python3
"""check-docs-sync.py — B8 doc/loop synchronization gate.

Enforces that every B8 "source of truth" doc agrees on the loop-harness stage order,
the `loop-ts-floor` guard, and the B-behaviour range upper bound. Fails (non-zero exit)
when any of them drift.

On drift it invokes the project-manager Hermes CLI (`hermes -z`) with a prompt describing
the exact drift, scoped to the CURRENT WORKING DIRECTORY (the path where the command was
asked), so the human gets an actionable natural-language explanation.

This is hermetic: it reads only local files and (optionally) shells out to `hermes` for the
drift report. No network, no Ollama, no git tree writes.

Usage:
    python3 scripts/check-docs-sync.py            # exit 0 if all sync files agree
    make check-docs-sync                          # same, via Makefile
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

# Sync files (relative to repo root). These are the B8 "source of truth" docs.
# docs/openspec-engineering-loop-harness.md is named by B8 itself as the
# authoritative reference, so it is included here — a drift there is caught.
SYNC_FILES = [
    "Makefile",
    "AGENTS.md",
    "hermes/skills/openspec-loop-harness.md",
    "scripts/run-loop-harness.sh",
    "docs/openspec-engineering-loop-harness.md",
]
# Narrative docs that MUST declare the full B-behaviour range (B1 up to B_RANGE_MIN).
NARRATIVE_FILES = {
    "AGENTS.md",
    "hermes/skills/openspec-loop-harness.md",
    "docs/openspec-engineering-loop-harness.md",
}

# LEGACY FALLBACK constants. The live contract is DERIVED from the source of truth
# (see derive_contract) so a doc evolution (B26, new stage) needs NO constant edit —
# only `make regen-doc-sync-fixtures`. These defaults apply only if a source can't
# be parsed, so the gate never crashes on a malformed input.
CANONICAL_STAGE_ORDER_FALLBACK = [
    "loop-collect",
    "loop-ts-floor",
    "loop-unit",
    "loop-unit-real",
    "loop-e2e",
    "loop-integration",
    "loop-build-app",
    "loop-test-app",
]
B_RANGE_MIN_FALLBACK = 25


def derive_contract(repo_root: Path) -> tuple[list[str], int]:
    """Derive the B8 contract from the AUTHORITATIVE sources, NOT hardcoded constants.

    - stage order: parsed from `scripts/run-loop-harness.sh` STAGES=(...), with the
      final `check-docs-sync` gate stage dropped (that is the gate itself, not a loop stage).
    - B-range upper bound: max B<digit> referenced across the narrative sync docs
      (they literally declare the range, e.g. "B1-B25").

    Falls back to the legacy constants if a source can't be parsed, so the gate never
    crashes. This is what makes the gate self-update when the harness/docs evolve:
    bump AGENTS.md to B26 and the gate follows — no Python edit required.
    """
    stages = list(CANONICAL_STAGE_ORDER_FALLBACK)
    runner = repo_root / "scripts/run-loop-harness.sh"
    if runner.exists():
        txt = runner.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"STAGES=\(([^)]*)\)", txt)
        if m:
            parsed = m.group(1).split()
            if parsed and parsed[-1] == "check-docs-sync":
                parsed = parsed[:-1]  # drop the gate itself
            if len(parsed) >= 2:
                stages = parsed

    max_b = B_RANGE_MIN_FALLBACK
    found: list[int] = []
    for rel in NARRATIVE_FILES:
        p = repo_root / rel
        if p.exists():
            for mm in re.finditer(r"B(\d+)", p.read_text(encoding="utf-8", errors="replace")):
                try:
                    found.append(int(mm.group(1)))
                except ValueError:
                    continue
    if found:
        max_b = max(found)
    return stages, max_b


def log(msg: str) -> None:
    print(f"[check-docs-sync] {msg}", flush=True)


def find_repo_root(start: Path) -> Path | None:
    """Probe upward for a dir containing BOTH AGENTS.md and Makefile (the repo root)."""
    cur = start.resolve()
    for _ in range(10):
        if (cur / "AGENTS.md").exists() and (cur / "Makefile").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def normalize(text: str) -> str:
    """Normalize so the canonical stage chain can be matched regardless of glyph/spacing.

    - arrow glyphs -> ascii `->`
    - en/em dashes -> hyphen
    - strip markdown backticks
    - strip parenthetical descriptions between stages, e.g.
      `loop-collect (hermetic ...) -> loop-ts-floor (STRICT ...)` -> `loop-collect -> loop-ts-floor`
    - collapse whitespace to single spaces
    This lets the backticked-arrow prose, the runner comment, and the Makefile header all
    collapse to one canonical chain.
    """
    import re
    text = text.replace("→", "->")
    text = text.replace("–", "-")  # en-dash
    text = text.replace("—", "-")  # em-dash
    text = text.replace("`", "")   # strip markdown backticks
    text = re.sub(r"\([^)]*\)", " ", text)  # drop parenthetical descriptions
    text = re.sub(r"\s+", " ", text)        # collapse whitespace
    return text


def ordered_stages_present(text: str, stages: list[str] | None = None) -> bool:
    """True if the canonical stage chain appears as a contiguous ordered substring
    (after glyph normalization), so removing `loop-ts-floor` from the chain fails even
    if the token appears elsewhere in the file.
    `stages` defaults to the derived canonical order (drop the gate itself).
    """
    if stages is None:
        stages = CANONICAL_STAGE_ORDER_FALLBACK
    norm = normalize(text)
    chain = " -> ".join(stages)
    return chain in norm


def b_range_ok(text: str, b_min: int | None = None) -> bool:
    """True if a B-behaviour range with upper bound >= b_min is present.

    IMPORTANT: matched on the RAW text (not normalize()), because normalize() strips
    parentheticals — and the Makefile's B1-B25 lives INSIDE a (...) prompt-string block
    that would otherwise be deleted. Glyph-tolerant: handles hyphen AND en-dash (B1-B25
    / B1–B25) and optional spaces.
    `b_min` defaults to the derived fallback bound (from derive_contract).
    """
    if b_min is None:
        b_min = B_RANGE_MIN_FALLBACK
    # match B1-B25 / B1–B25 / B1 - B25 (hyphen or en-dash, optional spaces)
    for m in re.finditer(r"B1\s*[-–]\s*B(\d+)", text):
        try:
            if int(m.group(1)) >= b_min:
                return True
        except ValueError:
            continue
    return False


def report_drift_via_hermes(drift_lines: list[str], cwd: Path,
                             stages: list[str], b_min: int) -> None:
    """Invoke the project-manager Hermes CLI with a drift prompt, scoped to `cwd`.

    Pattern mirrors scripts/record-work.py: select profile, then `hermes -z <prompt>`
    with cwd = the current working directory (the path where the command was asked).

    IMPORTANT: the gate must return its verdict IMMEDIATELY and never block on Hermes.
    So the Hermes call is DETACHED (Popen with start_new_session, output to a log) — we
    do NOT wait for it. The gate exits non-zero right after printing the drift.
    A slow/absent Hermes therefore can never stall the loop pre-flight.
    """
    stage_str = " -> ".join(stages)
    prompt = (
        "A B8 documentation-sync drift was detected in the obsidian-timestamp-utility "
        "repo. The loop/loop-harness docs are supposed to be ONE source of truth and "
        "must NOT drift. Below are the exact files + tokens that disagree. Explain, in "
        "plain language for a human engineer, what to fix in each file so they all match "
        f"the canonical {stage_str} order and the B-behaviour range up to at least B{b_min}. "
        "Be specific and concise.\n\n" + "\n".join(drift_lines)
    )
    log(f"detaching `hermes -z` (profile project-manager) for drift report, cwd={cwd}")
    log("  gate returns FAIL immediately; Hermes reports asynchronously when ready.")
    try:
        # Detach so the gate never blocks on a slow/attended Hermes run.
        shell_cmd = (
            f'hermes profile use project-manager && '
            f'hermes -z {shlex.quote(prompt)}'
        )
        log_path = Path(tempfile.gettempdir()) / "check-docs-sync-hermes.log"
        with open(log_path, "ab") as fh:
            subprocess.Popen(
                ["bash", "-c", shell_cmd],
                cwd=str(cwd),
                stdout=fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={**os.environ, "HERMES_PROFILE": "project-manager"},
            )
        log(f"  hermes drift report launching in background -> {log_path}")
    except (OSError, ValueError) as exc:
        log(f"warn: could not detach hermes ({exc}); gate still fails.")


def missing_make_targets(makefile_text: str, stages: list[str]) -> list[str]:
    """Return the canonical stages that are NOT declared as a `name:` make target
    in the Makefile text. This is the hard guarantee the user asked for: the gate
    must catch a *missing make command* (a target deleted from the Makefile), not
    just a missing chain *comment* string. The canonical stages are derived from
    the runner's STAGES array, so this stays in sync automatically."""
    missing = []
    for s in stages:
        if not re.search(rf"^{re.escape(s)}:", makefile_text, re.MULTILINE):
            missing.append(s)
    return missing


def check_docs_sync(repo_root: Path, cwd: Path) -> list[str]:
    # cwd = the path where THIS command was asked (per-path scoping for Hermes).
    cwd = Path.cwd()
    # DERIVE the contract from the source of truth so doc evolution (B26, new
    # stage) is followed automatically — no hardcoded constant to maintain.
    stages, b_min = derive_contract(repo_root)
    GUARD_TOKEN = "loop-ts-floor"
    drift: list[str] = []
    for rel in SYNC_FILES:
        path = repo_root / rel
        if not path.exists():
            drift.append(f"MISSING FILE: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        problems: list[str] = []
        if not ordered_stages_present(text, stages):
            problems.append("8-stage order (loop-collect->loop-ts-floor->...->loop-test-app) missing/misordered")
        if GUARD_TOKEN not in text:
            problems.append(f"guard token {GUARD_TOKEN!r} missing")
        # B-range applies to ALL sync files (no longer exempting Makefile/runner):
        # a stale B1-B21 in the Makefile commit-prompt is real drift.
        if not b_range_ok(text, b_min):
            problems.append(f"B-behaviour range up to >=B{b_min} missing")
        # Makefile-specific: every canonical stage MUST exist as a real `name:`
        # target. This catches a *deleted make command* — the gate must not pass
        # just because the chain comment string is still present.
        if rel == "Makefile":
            miss = missing_make_targets(text, stages)
            if miss:
                problems.append("missing make target(s): " + ", ".join(miss))
        if problems:
            drift.append(f"DRIFT in {rel}: " + "; ".join(problems))
    return drift


def main() -> int:
    cwd = Path.cwd().resolve()
    repo_root = find_repo_root(cwd)
    if repo_root is None:
        log(f"ERROR: could not locate repo root from {cwd} "
            "(need a dir containing both AGENTS.md and Makefile)")
        return 2

    problems = check_docs_sync(repo_root, cwd)
    if not problems:
        print("[check-docs-sync] PASS — all B8 sync files agree on stage order, "
              "guard, and B-range.")
        return 0

    print("[check-docs-sync] FAIL — B8 doc/loop sync drift detected:")
    for line in problems:
        print(f"[check-docs-sync]   - {line}")
    stages, b_min = derive_contract(repo_root)
    report_drift_via_hermes(problems, cwd, stages, b_min)
    return 1


if __name__ == "__main__":
    sys.exit(main())
