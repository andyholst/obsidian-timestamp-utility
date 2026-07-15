"""
E2E integration test for the GREETINGS OpenSpec change, run through the SAME harness as
ticket20/ticket22 (``run_pipeline_isolated``).

Unlike the ticket tests (which seed a change from a GitHub issue via the OpenSpec CLI), the
greetings change is a hand-authored LOCAL OpenSpec change
(``openspec/changes/greetings-modal-agentic-generation``). This test drives the agentic
pipeline against it end to end and asserts the deterministic-floor output honors the change's
Contract EXACTLY: command ``insert-greetings`` / ``Show Greetings`` opening a ``GreetingsModal``
that renders ``Greetings command obsidian plugin``.

This is the SIMPLE proof-of-concept companion to the ticket20/ticket22 e2e: it proves the slimmed
Python agentic pipeline (python-agentic-slim-refactor) still behaves per harness + loop + OpenSpec
engineering for a non-algorithmic (no CONTRACT_GENERATOR) feature.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from _e2e_helpers import run_pipeline_isolated, assert_modal_wired  # noqa: E402


GREETINGS_CHANGE = "greetings-modal-agentic-generation"


@pytest.mark.integration
@pytest.mark.e2e
def test_greetings_generates_via_local_openspec_change():
    """Run the agentic pipeline against the local greetings OpenSpec change and verify the contract."""
    # 1) Run the pipeline in an isolated temp dir against the hand-authored LOCAL change.
    #    run_pipeline_isolated copies openspec/changes/<change> into the temp PROJECT_ROOT, so
    #    generation runs fully locally (no GitHub, no MCP) -- exactly `make run-agentics CHANGE=`.
    result = run_pipeline_isolated(change=GREETINGS_CHANGE)
    assert result["returncode"] == 0, (
        f"Pipeline failed (rc={result['returncode']}):\n{result['stderr'][-3000:]}"
    )

    code = result["generated_code"]
    tests = result["generated_tests"]

    # 2) Generic harness invariant (B2): a Modal subclass wired via this.addCommand.
    assert_modal_wired(code)

    # 3) Spec-exact contract (the OpenSpec spec wins -- deterministic floor injects these verbatim).
    assert "insert-greetings" in code, "command id 'insert-greetings' missing from generated main.ts"
    assert "Show Greetings" in code, "command name 'Show Greetings' missing from generated main.ts"
    assert "GreetingsModal" in code, "GreetingsModal class missing from generated main.ts"
    assert "Greetings command obsidian plugin" in code, (
        "GreetingsModal.onOpen() must render 'Greetings command obsidian plugin'"
    )

    # 4) Exactly ONE GreetingsModal + ONE insert-greetings command (B7 sole-writer idempotency).
    assert code.count("class GreetingsModal") == 1, (
        f"expected exactly ONE GreetingsModal class, found {code.count('class GreetingsModal')}"
    )
    _cmd_count = code.count("id: 'insert-greetings'")
    assert _cmd_count == 1, (
        f"expected exactly ONE insert-greetings command, found {_cmd_count}"
    )

    # 5) Test contract present in the generated tests.
    assert "insert-greetings" in tests, "generated main.test.ts does not exercise insert-greetings"
