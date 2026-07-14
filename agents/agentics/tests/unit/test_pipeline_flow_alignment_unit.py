"""Hermetic flow-alignment test for the agentic pipeline (python-agentic-slim-refactor §3B.3).

Asserts the CANONICAL pipeline flow (tasks.md §3A) is present in BOTH LangGraph builders in
``composable_workflows.py`` so no refactor step silently drops a flow node/edge. This is the
machine check that keeps the Python code aligned 1:1 with the markdown engineering docs
(AGENTS.md Phases 2-7 + B1-B18; docs/openspec-engineering-loop-harness.md).

Pure source-inspection (no LLM / network / FS side-effects) — safe in any suite.
"""

import os
import re

HERE = os.path.dirname(__file__)
SRC = os.path.abspath(os.path.join(HERE, "..", "..", "src"))
CW = os.path.join(SRC, "composable_workflows.py")


def _source() -> str:
    with open(CW, "r", encoding="utf-8") as fh:
        return fh.read()


# Canonical nodes of the integration & testing loop (AGENTS.md Phase 6 / B6 self-correct).
INTEGRATION_NODES = [
    "code_integrator",
    "dependency_installer",
    "pre_test_runner",
    "post_test_runner",
    "error_recovery",
    "hitl",
    "code_reviewer",
    "output_result",
]

# Canonical nodes of the three-phase full workflow (AGENTS.md Phases 2-6 / B15 seed).
FULL_WORKFLOW_NODES = [
    "issue_processing",
    "dependency_analysis",
    "code_generation",
    "integration_testing",
]


def test_integration_loop_nodes_present():
    src = _source()
    for node in INTEGRATION_NODES:
        assert f'add_node("{node}"' in src, f"canonical integration node missing: {node}"


def test_full_workflow_nodes_present():
    src = _source()
    for node in FULL_WORKFLOW_NODES:
        assert f'add_node("{node}"' in src, f"canonical full-workflow node missing: {node}"


def test_bounded_self_correct_loop_edge_present():
    """Loop engineering (AGENTS.md B6): post_test_runner routes to error_recovery, which loops
    back to code_integrator; the router bounds the attempts."""
    src = _source()
    assert 'add_edge("error_recovery", "code_integrator")' in src, (
        "self-correct loop-back edge (error_recovery -> code_integrator) missing"
    )
    assert "recovery_router" in src, "bounded recovery_router missing"
    # bound present: attempts < N guard
    assert re.search(r"attempts\s*<\s*\d+", src), "recovery attempt bound missing"


def test_sole_writer_and_openspec_seed_referenced():
    """Harness B7/B10/B11 sole-writer + B15 OpenSpec seed must be documented in the code so the
    flow stays aligned with the markdown docs."""
    src = _source()
    assert "code_integrator" in src, "sole-writer node missing"
    # The doc-alignment comments cite the behaviours (code <-> markdown alignment).
    assert "SOLE writer" in src or "sole-writer" in src, "sole-writer doc ref missing"
    assert "B15" in src, "OpenSpec-seed (B15) doc ref missing"


def test_docs_alignment_comments_reference_agents_md():
    src = _source()
    assert "AGENTS.md" in src, "code must cite AGENTS.md phases/behaviours (code<->doc alignment)"
    assert "§3A" in src or "tasks.md" in src, "code must cite the canonical-flow tasks section"
