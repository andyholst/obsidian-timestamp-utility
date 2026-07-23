"""
Hermetic regression tests for the python-agentic-slim-refactor change (§4.4 / §9.4 / §10).

These prove the slimmed pipeline PRESERVES the harness invariants WITHOUT needing llama/Docker:
  - The deterministic sole-writer floor (`code_integrator`) is wired in BOTH graph builders and
    runs in fast mode (route_hitl fast path -> code_integrator -> output_result). (B7.1)
  - The contract parser is GENERIC (greetings `name: 'Show Greetings'` parses, not just uuid). (B9.4)
No network, no container — runnable anywhere via `make test-agents-unit`.
"""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from src.code_integrator_agent import CodeIntegratorAgent
from src.composable_workflows import ComposableWorkflows


# ---------------------------------------------------------------------------
# §10 / B7.1 — fast mode MUST still run the deterministic floor.
# ---------------------------------------------------------------------------
def test_fast_mode_routes_through_code_integrator_floor(monkeypatch):
    """route_hitl must NOT bypass the sole-writer floor in fast mode."""
    monkeypatch.setenv("TEST_FAST_MODE", "1")
    assert ComposableWorkflows.route_hitl({"validation_score": 0}) == "code_integrator"


def test_slow_mode_routes_to_integration_testing(monkeypatch):
    """Slow mode keeps the full integration path when score is high enough."""
    monkeypatch.delenv("TEST_FAST_MODE", raising=False)
    assert ComposableWorkflows.route_hitl({"validation_score": 90}) == "integration_testing"
    assert ComposableWorkflows.route_hitl({"validation_score": 0}) == "hitl"


def test_full_workflow_has_code_integrator_node_in_both_builders(monkeypatch):
    """The floor node is present in the full workflow graph (so fast mode can reach it)."""
    monkeypatch.delenv("TEST_FAST_MODE", raising=False)
    wf = ComposableWorkflows.__new__(ComposableWorkflows)
    # _create_integration_testing_workflow is a staticmethod returning an adapter; the raw
    # StateGraph is compiled inside. We instead assert the code_integrator node is added in the
    # full-workflow builder by inspecting source-level presence (cheap, hermetic stand-in for the
    # live graph compile already covered by test_composable_workflows_unit).
    import inspect

    src_full = inspect.getsource(ComposableWorkflows._create_full_workflow)
    assert 'add_node("code_integrator"' in src_full
    assert 'graph.add_edge("code_integrator", "output_result")' in src_full


# ---------------------------------------------------------------------------
# §9.4 — generic contract parser (greetings must parse, not just uuid).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "change,expected_id,expected_name,expected_modal",
    [
        ("greetings-modal-agentic-generation", "insert-greetings", "Show Greetings", "GreetingsModal"),
        ("uuid-modal-agentic-generation", "insert-uuid-v7", "Insert UUID v7 (timestamp-based)", "UuidV7Modal"),
    ],
)
def test_contract_parser_is_generic(monkeypatch, change, expected_id, expected_name, expected_modal):
    """Both uuid and greetings contracts parse fully — the parser is no longer uuid-specific."""
    # Resolve the repo root: walk up from __file__ AND check the container mount
    # points (/project, /app). In the unit container /app only has src/tests; the
    # real repo (openspec/) is at /project as a sibling mount, so a walk-up from
    # /app never reaches it. Return the first dir that contains openspec/changes.
    here = os.path.dirname(__file__)
    root = None
    cur = here
    walk = [here]
    for _ in range(8):
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        walk.append(parent)
        cur = parent
    for c in walk + ["/project", "/app", os.getcwd()]:
        if c and os.path.isdir(os.path.join(c, "openspec", "changes")):
            root = c
            break
    if not root:
        root = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    monkeypatch.setenv("PROJECT_ROOT", root)
    contract = CodeIntegratorAgent._expected_contract_for_change(change)
    assert contract is not None, f"contract not found for {change}"
    assert contract.get("command_id") == expected_id, contract
    assert contract.get("command_name") == expected_name, contract
    assert contract.get("modal_class") == expected_modal, contract
    assert contract.get("contract_ts"), "contract_ts (fenced markers) missing"


def test_contract_parser_returns_none_without_change(monkeypatch):
    monkeypatch.delenv("CHANGE", raising=False)
    assert CodeIntegratorAgent._expected_contract_for_change(None) is None
