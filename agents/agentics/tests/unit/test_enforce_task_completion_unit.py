"""
Unit tests for the task-completion guard (enforce-task-completion-gate).

Verifies `openspec_loader.open_task_count` and `assert_no_open_tasks`:
- counts only genuine unchecked `- [ ]` items
- ignores checkbox-like lines inside fenced ``` code blocks
- `assert_no_open_tasks` raises on open tasks, passes when all ticked
Hermetic: uses a temp dir, no repo / network / Ollama.
"""
import os
import sys
import tempfile
import textwrap

import pytest

# Make the agentics src importable without the full package layout.
AGENTICS_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "src")
)
if AGENTICS_SRC not in sys.path:
    sys.path.insert(0, AGENTICS_SRC)

from openspec_loader import assert_no_open_tasks, open_task_count  # noqa: E402


def _make_change(tmp_root, name, tasks_body):
    d = os.path.join(tmp_root, "openspec", "changes", name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "tasks.md"), "w") as f:
        f.write(tasks_body)
    return d


def test_open_task_count_counts_unchecked_only():
    with tempfile.TemporaryDirectory() as tmp:
        _make_change(
            tmp,
            "c1",
            textwrap.dedent(
                """
                # Tasks
                - [ ] 1.1 do a
                - [x] 1.2 done b
                - [ ] 1.3 do c
                """
            ),
        )
        assert open_task_count("c1", project_root=tmp) == 2


def test_open_task_count_ignores_fenced_code_blocks():
    with tempfile.TemporaryDirectory() as tmp:
        _make_change(
            tmp,
            "c2",
            textwrap.dedent(
                """
                - [ ] 1.1 genuine open task
                ```ts
                - [ ] this is inside a code fence, not a task
                - [ ] neither is this
                ```
                - [ ] 2.1 another genuine open task
                """
            ),
        )
        # The two fenced `- [ ]` lines must NOT count.
        assert open_task_count("c2", project_root=tmp) == 2


def test_open_task_count_zero_when_all_ticked():
    with tempfile.TemporaryDirectory() as tmp:
        _make_change(
            tmp,
            "c3",
            textwrap.dedent(
                """
                - [x] 1.1 a
                - [x] 1.2 b
                """
            ),
        )
        assert open_task_count("c3", project_root=tmp) == 0


def test_assert_no_open_tasks_passes_when_ticked():
    with tempfile.TemporaryDirectory() as tmp:
        _make_change(tmp, "c4", "- [x] 1.1 done\n")
        # Should not raise.
        assert_no_open_tasks("c4", project_root=tmp)


def test_assert_no_open_tasks_raises_when_open():
    with tempfile.TemporaryDirectory() as tmp:
        _make_change(tmp, "c5", "- [ ] 1.1 not done\n")
        with pytest.raises(RuntimeError, match="REFUSE archive"):
            assert_no_open_tasks("c5", project_root=tmp)


def test_open_task_count_missing_change_returns_zero():
    with tempfile.TemporaryDirectory() as tmp:
        assert open_task_count("does-not-exist", project_root=tmp) == 0
