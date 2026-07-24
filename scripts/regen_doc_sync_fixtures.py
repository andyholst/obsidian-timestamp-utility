#!/usr/bin/env python3
"""Regenerate the doc-sync test fixtures from the CURRENT real .md source-of-truth.

Run via `make regen-doc-sync-fixtures`. This keeps tests/test_check_docs_sync.py
honest over time: whenever AGENTS.md / the skill / the harness doc change (incl.
a NEW harness/loop rule like B26), re-run this to refresh the byte-copies, then
`make test-check-docs-sync` proves the rebuild is still correct (integrity +
semantic-accuracy tests).

ZERO manual maintenance on evolution: the drift anchors are DERIVED from the live
doc, not hardcoded. E.g. the B-range drift takes the CURRENT max-B phrase in
AGENTS.md ("B1-B25") and lowers the bound by one ("B1-B24"), so when the doc
advances to B26 the drift fixture auto-becomes "B1-B25" — no constant edit.

CRITICAL anchor check: the drift substitution's OLD string must STILL EXIST in the
current real doc (and the derived new bound must be >= 2 so the drift is real).
If a future doc restructure removes the phrase, this script FAILS loudly instead of
silently producing a fixture identical to aligned (which would fake 100% accuracy).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures" / "check_docs_sync"

MD_FILES = [
    "AGENTS.md",
    "hermes/skills/openspec-loop-harness.md",
    "docs/openspec-engineering-loop-harness.md",
]

# Aligned scenarios: literal byte-copies of the current real .md files.
ALIGNED = ["in_sync", "in_sync_ascii", "in_sync_en_dash"]


def _copy_real(rel: str, dst: Path) -> None:
    src = REPO / rel
    assert src.exists(), f"source missing: {src}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def _derive_b_range_drift(rel: str) -> tuple[str, str]:
    """Derive the B-range drift anchor from the CURRENT doc.

    Picks the B-range phrase with the **highest upper bound** in the doc,
    lowers its upper bound by one, and returns (old_phrase, new_phrase).
    This ensures the gate's b_range_ok check will catch the drift even in
    files where multiple B-range phrases exist (e.g. AGENTS.md with both
    B1–B32 and B1–B31).  Unique-anchor selection was removed because it
    caused the gate to miss drift when the unique anchor was lower than the
    main B-range.

    Anchor check: old must exist in the doc; new bound must stay >= 2 so
    the drift is real.
    """
    text = (REPO / rel).read_text(encoding="utf-8")
    # Gather every B1[-–]B<d> phrase and how many times it occurs.
    counts: dict[str, int] = {}
    for m in re.finditer(r"B1\s*[-–]\s*B(\d+)", text):
        phrase = m.group(0)
        counts[phrase] = counts.get(phrase, 0) + 1

    # Always use the phrase with the highest upper bound.
    def _upper_of(p: str) -> int:
        return int(p.split("B")[-1])

    phrase = max(counts, key=_upper_of)

    assert phrase in text, (
        f"no 'B1-B<d>' range phrase found in current {rel} — the doc was "
        f"restructured. The B-range drift scenario can no longer be produced. "
        f"Update the drift definition in scripts/regen_doc_sync_fixtures.py AND "
        f"the matching test in tests/test_check_docs_sync.py before regenerating."
    )
    upper = int(re.search(r"B(\d+)$", phrase).group(1))
    new_upper = upper - 1
    assert new_upper >= 2, (
        f"derived B-range drift would lower the bound to {new_upper} (from {upper}) "
        f"in {rel} — that is not a meaningful drift. The doc's range is too low."
    )
    # Lower the upper-bound B<d> in the phrase, leaving the 'B1' prefix intact.
    matches = list(re.finditer(r"B(\d+)", phrase))
    assert matches, f"no B<d> found in derived phrase {phrase!r}"
    upper_match = matches[-1]
    new_upper = int(upper_match.group(1)) - 1
    assert new_upper >= 2, (
        f"derived B-range drift would lower the bound to {new_upper} "
        f"(from {upper_match.group(1)}) in {rel} — not a meaningful drift."
    )
    new_phrase = phrase[:upper_match.start()] + f"B{new_upper}" + phrase[upper_match.end():]
    assert phrase in text, f"derived anchor {phrase!r} not found (should be present)"
    return phrase, new_phrase


def _remove_loop_e2e(text: str) -> tuple[str, int]:
    """Derive the stage-removal drift: remove every `→ `loop-e2e`` token (which
    breaks the canonical contiguous stage chain) and return (new_text, count).
    Anchor check: at least one `→ `loop-e2e`` must exist in the current doc.
    """
    anchor = "→ `loop-e2e`"
    count = text.count(anchor)
    assert count >= 1, (
        f"no '→ `loop-e2e`' token found in current doc — the canonical stage "
        f"chain was restructured. The stage-removal drift scenario can no longer "
        f"be produced. Update scripts/regen_doc_sync_fixtures.py before regenerating."
    )
    return text.replace(anchor, ""), count


def regen() -> None:
    if FIXTURES.exists():
        shutil.rmtree(FIXTURES)
    FIXTURES.mkdir(parents=True)

    for scenario in ALIGNED:
        d = FIXTURES / scenario
        d.mkdir(parents=True)
        for rel in MD_FILES:
            _copy_real(rel, d / rel)

    # Drift scenario 1: B-range lowered in EVERY sync .md file (derived from the
    # live doc, applied per-file). Proves the gate goes RED when ANY file's
    # B-range falls behind — not just AGENTS.md.
    d = FIXTURES / "drift_b_range_low"
    d.mkdir(parents=True)
    b_anchors = {}
    for rel in MD_FILES:
        _copy_real(rel, d / rel)
        old, new = _derive_b_range_drift(rel)
        b_anchors[rel] = (old, new)
        p = d / rel
        p.write_text(p.read_text(encoding="utf-8").replace(old, new))

    # Drift scenario 2: a stage (loop-e2e) REMOVED from the canonical chain in
    # EVERY sync .md file. Proves the gate reacts when a B-step / stage is pulled
    # out of ANY of the three docs.
    d = FIXTURES / "drift_stage_removed"
    d.mkdir(parents=True)
    for rel in MD_FILES:
        _copy_real(rel, d / rel)
        p = d / rel
        new_text, _ = _remove_loop_e2e(p.read_text(encoding="utf-8"))
        p.write_text(new_text)

    # Drift scenario 3: the CANONICAL stage chain reordered -> the gate MUST detect
    # it (RED). We swap the contiguous `loop-ts-floor`/`loop-unit` adjacency inside
    # the chain prefix (which appears on a single line in AGENTS.md), breaking the
    # canonical order. This is a REAL detection case, not a false positive.
    d = FIXTURES / "drift_reorder"
    d.mkdir(parents=True)
    for rel in MD_FILES:
        _copy_real(rel, d / rel)
    text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    old_chain = "`loop-collect` → `loop-ts-floor` → `loop-unit`"
    new_chain = "`loop-collect` → `loop-unit` → `loop-ts-floor`"
    assert old_chain in text, (
        "canonical chain prefix '`loop-collect` → `loop-ts-floor` → `loop-unit`' "
        "no longer found in current AGENTS.md — the doc was restructured. Update the "
        "reorder drift in scripts/regen_doc_sync_fixtures.py before regenerating."
    )
    ag = d / "AGENTS.md"
    ag.write_text(ag.read_text(encoding="utf-8").replace(old_chain, new_chain))

    print(f"Regenerated fixtures under {FIXTURES}")
    print(f"  aligned:   {', '.join(ALIGNED)}")
    print(f"  drifted:   drift_b_range_low (B-range {b_anchors['AGENTS.md'][0]}' -> "
          f"'{b_anchors['AGENTS.md'][1]}' in ALL 3 .md files), "
          f"drift_stage_removed (loop-e2e removed from chain in ALL 3 .md files), "
          f"drift_reorder (secondary mention only)")
    print("Run `make test-check-docs-sync` to verify the rebuild.")


if __name__ == "__main__":
    regen()
