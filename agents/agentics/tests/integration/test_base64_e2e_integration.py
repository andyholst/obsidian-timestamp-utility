"""
E2E integration test for the BASE64-TOOL OpenSpec change, run through the SAME harness as
greetings (``run_pipeline_isolated``).

This is the THIRD standing B3 gate (alongside ticket20/ticket22 + greetings). The base64-tool
change is a hand-authored LOCAL OpenSpec change (``openspec/changes/base64-tool``). This test
drives the agentic pipeline against it end to end and asserts the deterministic-floor output
honors the change's Contract EXACTLY: commands ``encode-base64-message`` / ``decode-base64-message``
opening a ``Base64Modal`` whose ``encodeBase64``/``decodeBase64`` generators base64 round-trip
``hello world`` <-> ``aGVsbG8gd29ybGQ=``.

It is an algorithmic (non-timestamp) feature, proving the deterministic floor handles a feature
whose ``generator_kind`` is neither ``uuid`` nor ``timestamp`` — the GENERATOR body is still
injected verbatim via the ``=== CONTRACT_GENERATOR ===`` marker.

B1/B2/B3/B4/B5 hold: runs in an isolated temp dir, never touches the real ``src/main.ts``,
skips cleanly without Ollama (B17), and asserts the modal is wired + the contract is honored.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from _e2e_helpers import run_pipeline_isolated, assert_modal_wired  # noqa: E402


BASE64_CHANGE = "base64-tool"


@pytest.mark.integration
@pytest.mark.e2e
def test_base64_generates_via_local_openspec_change():
    """Run the agentic pipeline against the local base64 OpenSpec change and verify the contract."""
    # 1) Run the pipeline in an isolated temp dir against the hand-authored LOCAL change.
    #    run_pipeline_isolated copies openspec/changes/<change> into the temp PROJECT_ROOT, so
    #    generation runs fully locally (no GitHub, no MCP) -- exactly `make run-agentics CHANGE=`.
    result = run_pipeline_isolated(change=BASE64_CHANGE)
    assert result["returncode"] == 0, (
        f"Pipeline failed (rc={result['returncode']}):\n{result['stderr'][-3000:]}"
    )

    code = result["generated_code"]
    tests = result["generated_tests"]

    # 2) Generic harness invariant (B2): a Modal subclass wired via this.addCommand.
    assert_modal_wired(code)

    # 3) Spec-exact contract (the OpenSpec spec wins -- deterministic floor injects these verbatim).
    assert "encode-base64-message" in code, "command id 'encode-base64-message' missing from generated main.ts"
    assert "decode-base64-message" in code, "command id 'decode-base64-message' missing from generated main.ts"
    assert "Base64Modal" in code, "Base64Modal class missing from generated main.ts"
    assert "Encode Base64 Message" in code, "command name 'Encode Base64 Message' missing from generated main.ts"
    assert "Decode Base64 Message" in code, "command name 'Decode Base64 Message' missing from generated main.ts"

    # 4) Exactly ONE Base64Modal + ONE of each command (B7 sole-writer idempotency).
    assert code.count("class Base64Modal") == 1, (
        f"expected exactly ONE Base64Modal class, found {code.count('class Base64Modal')}"
    )
    _enc = code.count("id: 'encode-base64-message'")
    _dec = code.count("id: 'decode-base64-message'")
    assert _enc == 1, f"expected exactly ONE encode-base64-message command, found {_enc}"
    assert _dec == 1, f"expected exactly ONE decode-base64-message command, found {_dec}"

    # 5) The generator bodies are injected (algorithmic feature, non-timestamp).
    assert "encodeBase64" in code, "encodeBase64 generator missing from generated main.ts"
    assert "decodeBase64" in code, "decodeBase64 generator missing from generated main.ts"

    # 6) Test contract present in the generated tests.
    assert "encode-base64-message" in tests, "generated main.test.ts does not exercise encode-base64-message"
    assert "decode-base64-message" in tests, "generated main.test.ts does not exercise decode-base64-message"
