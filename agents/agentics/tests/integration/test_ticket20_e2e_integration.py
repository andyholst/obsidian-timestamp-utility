"""
E2E integration test for GitHub issue #20, driven as a LOCAL OpenSpec change.

Crucially, NO hand-authored ``openspec/changes/ticket20/`` exists in the repo. Instead this
test PROVES the agentic workflow from the user's requirement: when a GitHub issue comes in, the
pipeline's ``create_change_from_issue()`` uses the OpenSpec CLI (``openspec new change``) to
scaffold the change directory, then seeds proposal/spec/tasks from the issue -- and only THEN
does generation run, locally, against ``openspec:ticket20``. This test exercises exactly that
seed-then-generate path end to end, with no live GitHub fetch (we pass the issue content in).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from src.openspec_loader import create_change_from_issue  # noqa: E402

from _e2e_helpers import run_pipeline_isolated, assert_modal_wired, _repo_root  # noqa: E402


# The contract the OpenSpec spec (tasks.md) must pin so the deterministic floor injects the
# right command/Modal/generator. This is what a real GitHub issue's spec would contain.
TICKET20_ISSUE_BODY = """\
We need a command that inserts a UUID v7 (timestamp-based) at the cursor.

## Contract

```ts
// === CONTRACT_COMMAND ===
this.addCommand({
  id: 'insert-uuid-v7',
  name: 'Insert UUID v7 (timestamp-based)',
  callback: () => { this.generateUuidV7(); },
});
// === END_CONTRACT_COMMAND ===

// === CONTRACT_GENERATOR ===
generateUuidV7() {
  const uuid = this.getUuidV7();
  const activeFile = this.app.workspace.getActiveFile();
  if (activeFile) {
    const editor = this.app.workspace.getActiveViewOfType(require('obsidian').MarkdownView)?.editor;
    editor?.replaceSelection(uuid);
  }
}
// === END_CONTRACT_GENERATOR ===

// === CONTRACT_MODAL ===
class UuidV7Modal extends obsidian.Modal {
  constructor(app, onSubmit) { super(app); this.onSubmit = onSubmit; }
  onOpen() { const { contentEl } = this; contentEl.setText('UUID v7'); }
  onClose() { this.contentEl.empty(); }
}
// === END_CONTRACT_MODAL ===
```

## Test Contract

```ts
// === TEST_CONTRACT_INSERT ===
test('inserts a UUID v7 at the cursor', () => {
  const plugin = new MyPlugin(mockApp);
  const uuid = plugin.getUuidV7();
  expect(uuid).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-/);
});
// === END_TEST_CONTRACT_INSERT ===
```
"""


@pytest.mark.integration
@pytest.mark.e2e
def test_ticket20_generates_via_local_openspec_change():
    """Seed ticket20 from the issue (via OpenSpec CLI) then generate locally."""
    root = _repo_root()

    # 1) Mimic the pipeline: fetch the issue once, then seed a LOCAL OpenSpec change using the
    #    OpenSpec CLI (create_change_from_issue -> `openspec new change ticket20` + artifacts).
    change_name = create_change_from_issue(
        url="https://github.com/andyholst/obsidian-timestamp-utility/issues/20",
        issue_title="Implement Current TimeStamp as UUID",
        issue_body=TICKET20_ISSUE_BODY,
        project_root=root,
    )
    assert change_name == "ticket20"

    try:
        # 2) Run the agentic pipeline against the freshly-seeded LOCAL change (no live GitHub).
        result = run_pipeline_isolated(change=change_name)
        assert result["returncode"] == 0, (
            f"Pipeline failed (rc={result['returncode']}):\n{result['stderr'][-3000:]}"
        )
        # 3) The generated TS must honor the contract (Modal + command wired).
        assert_modal_wired(result["generated_code"])
    finally:
        # 4) Clean up the runtime-generated change dir (it was produced by the run, not authored).
        import shutil

        seeded = os.path.join(root, "openspec", "changes", change_name)
        if os.path.isdir(seeded):
            shutil.rmtree(seeded)
