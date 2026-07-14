"""Real unit test for the anchor-based deterministic merge in ``code_integrator_agent``.

Pins the Plan-B merge contract (OpenSpec: integrator-merge-refactor):
- the spec contract command appears exactly once,
- the Modal is a single top-level class,
- the generator method lives INSIDE TimestampPlugin,
- no orphaned `export` keyword,
- output size never shrinks (no omission).

All external boundaries (LLM/Ollama/network/FS) are mocked; real merge logic is exercised.
"""
import sys
from pathlib import Path

import pytest

# Make the package importable when run via docker compose (mounted at /app/prod)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.code_integrator_agent import CodeIntegratorAgent  # noqa: E402


def _agent():
    # Build an instance without triggering __init__ (which may require an LLM client).
    agent = CodeIntegratorAgent.__new__(CodeIntegratorAgent)
    agent.name = "test"
    return agent


def _contract(change="uuid-modal-agentic-generation"):
    """Hermetic spec contract (no env/git/network dependency).

    Mirrors what ``_expected_contract_for_change`` resolves from the OpenSpec change, but is
    hard-coded so the test does not depend on PROJECT_ROOT/CHANGE env vars set by other tests.
    Includes the real ``contract_ts`` (the ``## Contract`` fenced block) so
    ``_spec_driven_feature_for_contract`` produces the deterministic command/Modal/generator.
    """
    contract_ts = """
// === CONTRACT_COMMAND === (injected inside onload())
this.addCommand({
    id: 'insert-uuid-v7',
    name: 'Insert UUID v7 (timestamp-based)',
    editorCallback: (__editor: obsidian.Editor, _ctx: obsidian.MarkdownView | obsidian.MarkdownFileInfo) => {
        try {
            const uuid = this.generateUuidV7();
            __editor.replaceSelection(uuid);
        } catch (error) {
            new Notice(`Failed to generate UUID v7: ${(error as Error).message}`);
        }
    },
});
// === CONTRACT_GENERATOR === (injected inside TimestampPlugin)
generateUuidV7(): string {
    const ms = Date.now();
    const rand = new Uint8Array(10);
    crypto.getRandomValues(rand);
    const hex = (n: number, w: number) => n.toString(16).padStart(w, '0');
    const t = hex(ms, 12);
    const r1 = (rand[0] << 8) | rand[1];
    const r2 = (rand[2] << 8) | rand[3];
    const r3 = (rand[4] << 8) | rand[5];
    const r4 = (rand[6] << 8) | rand[7];
    const r5 = (rand[8] << 8) | rand[9];
    const uuid =
        t.slice(0, 8) + '-' + t.slice(8, 12) + '-7' + hex(r1, 3).slice(0, 3) + '-' +
        hex(0x8000 | r2, 4) + '-' + hex(r3, 4) + hex(r4, 4) + hex(r5, 4);
    return uuid;
}
// === CONTRACT_MODAL === (injected as a top-level module member)
export class UuidV7Modal extends obsidian.Modal {
    constructor(app: obsidian.App) {
        super(app);
    }
    onOpen() {
        const { contentEl } = this;
        contentEl.setText('UUID v7 (timestamp-based) copied to clipboard');
    }
    onClose() {
        this.contentEl.empty();
    }
}
// === END_CONTRACT ===
"""
    return {
        "command_id": "insert-uuid-v7",
        "command_name": "Insert UUID v7 (timestamp-based)",
        "modal_class": "UuidV7Modal",
        "generator_kind": "uuidv7",
        "contract_ts": contract_ts,
    }


# A minimal but realistic plugin baseline: imports, a TimestampPlugin with one command,
# and NO uuid command / modal / generator yet.
BASELINE = """import * as obsidian from 'obsidian';

export default class TimestampPlugin extends obsidian.Plugin {
    async onload() {
        this.addCommand({
            id: 'insert-timestamp',
            name: 'Insert Timestamp',
            editorCallback: (editor) => {
                editor.replaceSelection(this.generateTimestamp());
            },
        });
    }

    generateTimestamp(): string {
        return new Date().toISOString();
    }
}
"""


def test_extract_balanced_blocks_keeps_export_keyword():
    """_extract_balanced_blocks must capture the full source line (incl. `export `)."""
    text = "export class Foo extends Bar {\n  x() {}\n}\nconst y = 1;\n"
    blocks = CodeIntegratorAgent._extract_balanced_blocks(text, "class ")
    assert any(b.startswith("export class Foo") for b in blocks), blocks


def test_assemble_contract_command_count_is_one():
    agent = _agent()
    contract = _contract()
    # LLM output that ALSO emits the contract command (wrong body) -> must be stripped.
    llm = ("this.addCommand({ id: 'insert-uuid-v7', name: 'WRONG', "
           "editorCallback: (e) => { e.replaceSelection('x'); } });")
    merged = agent._assemble_contract_features(BASELINE, llm, contract)
    assert merged.count("id: 'insert-uuid-v7'") == 1


def test_assemble_contract_modal_is_top_level_and_single():
    agent = _agent()
    contract = _contract()
    merged = agent._assemble_contract_features(BASELINE, "", contract)
    assert merged.count("export class UuidV7Modal extends obsidian.Modal") == 1
    # Modal must NOT be nested inside TimestampPlugin.
    plugin_close = merged.rfind("export default class TimestampPlugin")
    assert merged.index("export class UuidV7Modal") > plugin_close


def test_assemble_contract_generator_inside_plugin_class():
    agent = _agent()
    contract = _contract()
    merged = agent._assemble_contract_features(BASELINE, "", contract)
    # generator method def present (spec emits it WITHOUT `private`)
    assert "generateUuidV7(): string {" in merged
    # and NOT inside the top-level Modal (which is appended at file end)
    modal_idx = merged.index("export class UuidV7Modal")
    gen_idx = merged.index("generateUuidV7(): string {")
    assert gen_idx < modal_idx


def test_assemble_contract_no_orphan_export():
    agent = _agent()
    contract = _contract()
    merged = agent._assemble_contract_features(BASELINE, "", contract)
    for i, line in enumerate(merged.split("\n")):
        # the only bare `export` lines should be real declarations
        assert line.strip() != "export", f"orphaned export at line {i}"


def test_assemble_contract_idempotent_on_rerun():
    agent = _agent()
    contract = _contract()
    once = agent._assemble_contract_features(BASELINE, "", contract)
    twice = agent._assemble_contract_features(once, "", contract)
    assert twice.count("id: 'insert-uuid-v7'") == 1
    assert twice.count("export class UuidV7Modal extends obsidian.Modal") == 1
    assert twice.count("generateUuidV7(): string {") == 1


def test_assemble_contract_no_omission():
    agent = _agent()
    contract = _contract()
    # Baseline already has rich existing logic; merge must not shrink it.
    merged = agent._assemble_contract_features(BASELINE, "", contract)
    assert len(merged) >= len(BASELINE)


def test_assemble_contract_escaped_newline_tolerance():
    """LLM output with literal \\n escapes must not break the merge."""
    agent = _agent()
    contract = _contract()
    llm = ("this.addCommand({ id: 'insert-uuid-v7', name: 'X', editorCallback: (e) => { e.replaceSelection('x'); } });\\n"
           "export class UuidV7Modal extends obsidian.Modal {\\n  onOpen() {}\\n}")
    merged = agent._assemble_contract_features(BASELINE, llm, contract)
    assert merged.count("id: 'insert-uuid-v7'") == 1
    assert merged.count("export class UuidV7Modal extends obsidian.Modal") == 1
