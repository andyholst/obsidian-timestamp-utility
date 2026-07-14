"""Regression test for the greetings (generator-less) contract path — bug 6.1.

The `greetings-modal-agentic-generation` change exposed that a contract WITHOUT a
`// === CONTRACT_GENERATOR ===` marker (a simple modal with no algorithmic body) was rejected by
`_spec_driven_feature_for_contract` (it required command+generator+modal), so the whole
deterministic contract-injection path fell back to a plain LLM merge — letting the LLM's
duplicate/non-contract Modal survive. The fix makes the GENERATOR optional (command + modal are
the only required pieces).

Hermetic: no LLM / network. Reads the real greetings change contract from the repo.

NOTE on harness hygiene: several OTHER unit tests in this suite mutate `os.environ["PROJECT_ROOT"]`
(e.g. to "/tmp", "/project", "/tmp/test_project") at import time, which would make
`_expected_contract_for_change` resolve the change dir against the wrong root and return None.
We therefore re-pin BOTH `PROJECT_ROOT` (real repo root) and `CHANGE` at the top of every test
function, so these regression tests are collection-order-independent and never silently pick up a
polluter's env.
"""

import os
import subprocess

from src.code_integrator_agent import CodeIntegratorAgent  # noqa: E402

CHANGE = "greetings-modal-agentic-generation"


def _repo_root() -> str:
    """Resolve the repo root reliably (in-container + local).

    In the unit-test container ``__file__`` is under ``/app/tests/unit/`` (only
    ``/app/src`` + ``/app/tests`` are mounted there); the real repo (with
    ``openspec/``) is mounted at ``/project`` as a SEPARATE (sibling) mount, so a
    naive walk-up from ``/app`` can never reach ``/project``. We therefore check the
    walk-up path AND the well-known container mount points (``/project``, ``/app``)
    and return the first one that actually contains ``openspec/changes``.
    """
    here = os.path.dirname(__file__)
    candidates = [here]
    cur = here
    for _ in range(8):
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        candidates.append(parent)
        cur = parent
    candidates += ["/project", "/app", os.getcwd()]
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, "openspec", "changes")):
            return c
    return os.path.abspath(os.path.join(here, "..", "..", "..", ".."))


_REPO_ROOT = _repo_root()


def _pin_env():
    os.environ["PROJECT_ROOT"] = _REPO_ROOT
    os.environ["CHANGE"] = CHANGE


def _agent():
    a = CodeIntegratorAgent.__new__(CodeIntegratorAgent)
    a.name = "CodeIntegrator"
    return a


def test_generatorless_contract_yields_feature():
    """A contract with a command + modal but NO generator must still produce a feature dict."""
    _pin_env()
    contract = CodeIntegratorAgent._expected_contract_for_change(CHANGE)
    assert contract is not None, "greetings contract not found — check the change exists"
    feat = _agent()._spec_driven_feature_for_contract(contract)
    assert feat, "generator-less contract wrongly rejected (bug 6.1 regression)"
    assert feat["command_body"], "command body missing"
    assert feat["modal_class"], "modal class missing"
    assert feat["generator_fn"] == "", "greetings has no generator; expected empty"


def test_assembly_injects_exactly_one_contract_modal():
    """Even when the LLM emits duplicate/non-contract modals, the deterministic floor must yield
    exactly ONE authoritative contract modal + command (harness B7 sole-writer idempotency)."""
    _pin_env()
    contract = CodeIntegratorAgent._expected_contract_for_change(CHANGE)
    existing = (
        "import * as obsidian from 'obsidian';\n"
        "export class TimestampPlugin extends obsidian.Plugin { async onload() {} }\n"
    )
    # LLM output carrying duplicate, non-contract modals — these must be discarded.
    llm = (
        "export class GreetingsModal extends obsidian.Modal { onOpen(){} }\n"
        "export class GreetingsModal extends obsidian.Modal { onOpen(){} }\n"
    )
    out = _agent()._assemble_contract_features(existing, llm, contract)
    assert out.count("class GreetingsModal extends obsidian.Modal") == 1, "duplicate modal (bug 6.1)"
    assert out.count("id: 'insert-greetings'") == 1, "duplicate/missing command"
    assert "Greetings command obsidian plugin" in out, "contract greeting text missing"


def test_contract_path_never_falls_back_to_llm_when_smaller():
    """Bug 6.4: when a contract is present, the deterministic assembly MUST win unconditionally.
    The assembled greetings file is legitimately SMALLER than the committed baseline (it strips
    the LLM's dead modal noise). The old size-guard fell back to the LLM on this shrink and wrote
    a 0-byte main.ts. Assert the deterministic path returns the contract output and the LLM
    fallback is never invoked, even when output < existing baseline."""
    from unittest.mock import MagicMock

    _pin_env()
    contract = CodeIntegratorAgent._expected_contract_for_change(CHANGE)
    # Real committed main.ts baseline (larger than the assembled greetings output).
    import subprocess as _sp, os as _os

    proj = _os.getenv("PROJECT_ROOT")
    head = _sp.run(
        ["git", "-c", "safe.directory=*", "-C", proj, "show", "HEAD:src/main.ts"],
        capture_output=True,
        text=True,
        env={**_os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
    )
    existing = head.stdout if head.returncode == 0 and head.stdout.strip() else ""
    agent = _agent()
    agent.llm = MagicMock()
    agent.integrate_code_with_llm = MagicMock(return_value="")
    out = agent.generate_updated_code_file(existing, "", contract)
    # The LLM fallback must NOT be used when a contract is present.
    agent.integrate_code_with_llm.assert_not_called()
    # The output must be the deterministic contract assembly, not empty.
    assert out.strip(), "contract path produced empty output (bug 6.4 regression)"
    assert "class GreetingsModal extends obsidian.Modal" in out, "contract modal missing"
    assert "id: 'insert-greetings'" in out, "contract command missing"


def test_test_contract_injection_balanced_braces():
    """Bug 6.6: `integrate_test_contract` (the spec-Test-Contract injector) must produce a
    brace-balanced `main.test.ts`. Its brace-counter was fooled by regex-literal braces inside
    the uuid tests (`toMatch(/^[0-9a-f]{8}-...{12}$/)`) AND the uuid-block strip close-condition
    only matched a bare `}` (not `});`), so the uuid block was not stripped and a stray close was
    dropped -> TS1005 '}' expected. Assert the injected file is balanced and the uuid block is gone
    while timestamp tests + the new greetings block survive."""
    import subprocess as _sp, os as _os

    _pin_env()
    contract = CodeIntegratorAgent._expected_contract_for_change(CHANGE)
    proj = _os.getenv("PROJECT_ROOT")
    head = _sp.run(
        ["git", "-c", "safe.directory=*", "-C", proj, "show", "HEAD:src/__tests__/main.test.ts"],
        capture_output=True,
        text=True,
        env={**_os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
    )
    base = head.stdout if head.returncode == 0 and head.stdout.strip() else ""
    agent = _agent()
    out = agent.integrate_test_contract(base, contract, baseline_content=base)
    assert out.count("{") == out.count("}"), f"unbalanced braces (bug 6.6): {out.count('{')} vs {out.count('}')}"
    assert "insert-uuid-v7" not in out, "uuid block should be stripped on feature switch"
    assert "insert-greetings" in out, "greetings contract block missing"
    assert "generateTimestamp" in out, "timestamp tests dropped by injector"
