"""
E2E integration test for GitHub issue #22, driven as a LOCAL OpenSpec change.

Like ticket20, NO hand-authored ``openspec/changes/ticket22/`` exists in the repo. This test
proves the seed-then-generate workflow: the pipeline's ``create_change_from_issue()`` uses the
OpenSpec CLI (``openspec new change``) to scaffold the change from the issue, then generation
runs locally against ``openspec:ticket22``. Distinct capability (random UUID) from ticket20, so
the two tests prove two independent local-change generations.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from src.openspec_loader import create_change_from_issue  # noqa: E402

from _e2e_helpers import run_pipeline_isolated, assert_modal_wired, _repo_root  # noqa: E402


TICKET22_ISSUE_BODY = """\
Add a second UUID command: insert a random (v4-layout) UUID at the cursor.

## Contract

```ts
// === CONTRACT_COMMAND ===
this.addCommand({
  id: 'insert-random-uuid',
  name: 'Insert Random UUID',
  callback: () => { this.generateRandomUuid(); },
});
// === END_CONTRACT_COMMAND ===

// === CONTRACT_GENERATOR ===
generateRandomUuid() {
  const uuid = this.getRandomUuid();
  const activeFile = this.app.workspace.getActiveFile();
  if (activeFile) {
    const editor = this.app.workspace.getActiveViewOfType(require('obsidian').MarkdownView)?.editor;
    editor?.replaceSelection(uuid);
  }
}
// === END_CONTRACT_GENERATOR ===

// === CONTRACT_MODAL ===
class RandomUuidModal extends obsidian.Modal {
  constructor(app, onSubmit) { super(app); this.onSubmit = onSubmit; }
  onOpen() { const { contentEl } = this; contentEl.setText('Random UUID'); }
  onClose() { this.contentEl.empty(); }
}
// === END_CONTRACT_MODAL ===
```

## Test Contract

```ts
// === TEST_CONTRACT_INSERT ===
test('inserts a random UUID at the cursor', () => {
  const plugin = new MyPlugin(mockApp);
  const uuid = plugin.getRandomUuid();
  expect(uuid).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-/);
});
// === END_TEST_CONTRACT_INSERT ===
```
"""


@pytest.mark.integration
@pytest.mark.e2e
def test_ticket22_generates_via_local_openspec_change():
    """Seed ticket22 from the issue (via OpenSpec CLI) then generate locally."""
    root = _repo_root()

    change_name = create_change_from_issue(
        url="https://github.com/andyholst/obsidian-timestamp-utility/issues/22",
        issue_title="Random UUID helper",
        issue_body=TICKET22_ISSUE_BODY,
        project_root=root,
    )
    assert change_name == "ticket22"

    try:
        result = run_pipeline_isolated(change=change_name)
        assert result["returncode"] == 0, (
            f"Pipeline failed (rc={result['returncode']}):\n{result['stderr'][-3000:]}"
        )
        assert_modal_wired(result["generated_code"])
    finally:
        import shutil

        seeded = os.path.join(root, "openspec", "changes", change_name)
        if os.path.isdir(seeded):
            shutil.rmtree(seeded)
