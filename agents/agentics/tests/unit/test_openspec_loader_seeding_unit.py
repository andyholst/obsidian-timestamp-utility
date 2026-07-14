"""Unit tests for openspec_loader change-seeding helpers.

These test the GitHub-ticket -> local OpenSpec change bridge:
- ``github_url_to_change_name`` (pure, deterministic).
- ``create_change_from_issue`` (shells out to the OpenSpec CLI, then writes artifacts).

External calls (the ``openspec`` CLI) are mocked; only real-logic behaviour is exercised.
"""

import os
import sys
import textwrap
from unittest.mock import patch, MagicMock

import pytest


# Ensure the agentics package is importable when run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from src.openspec_loader import (  # noqa: E402
    github_url_to_change_name,
    create_change_from_issue,
    find_change_dir,
    load_change,
    is_local_change_ref,
)


def test_github_url_to_change_name_derives_ticket_slug():
    url = "https://github.com/andyholst/obsidian-timestamp-utility/issues/20"
    assert github_url_to_change_name(url) == "ticket20"

    url22 = "https://github.com/andyholst/obsidian-timestamp-utility/issues/22"
    assert github_url_to_change_name(url22) == "ticket22"


def test_github_url_to_change_name_fallback_segment():
    # No /issues/<n> pattern -> uses last path segment sanitized.
    assert github_url_to_change_name("https://example.com/foo/bar.baz") == "bar-baz"


def test_is_local_change_ref_classifies():
    assert is_local_change_ref("openspec:ticket20") is True
    assert is_local_change_ref("ticket20") is True
    assert is_local_change_ref("https://github.com/o/r/issues/20") is False


def test_create_change_from_issue_invokes_cli_and_writes_artifacts(tmp_path):
    """create_change_from_issue must scaffold via `openspec new change` and write the artifacts."""
    # The OpenSpec CLI call is fully mocked (we never run the real binary in unit tests).
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Created change", stderr="")

        change = create_change_from_issue(
            url="https://github.com/andyholst/obsidian-timestamp-utility/issues/20",
            issue_title="Implement Current TimeStamp as UUID",
            issue_body="We need a UUID v7 insert command.",
            project_root=str(tmp_path),
        )

    assert change == "ticket20"
    # 1) The CLI was used to scaffold the change directory.
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[:3] == ["openspec", "new", "change"]
    assert "ticket20" in called_cmd

    change_dir = tmp_path / "openspec" / "changes" / "ticket20"
    # 2) The CLI owns the directory; content files were written by the loader.
    assert (change_dir / "proposal.md").is_file()
    assert (change_dir / "specs" / "ticket20" / "spec.md").is_file()
    assert (change_dir / "tasks.md").is_file()

    proposal = (change_dir / "proposal.md").read_text()
    assert "github.com" in proposal and "ticket20" in proposal
    tasks = (change_dir / "tasks.md").read_text()
    assert "openspec:ticket20" in tasks


def test_create_change_from_issue_is_idempotent(tmp_path):
    """Re-running on the same issue reuses the existing change (no second CLI scaffold)."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        first = create_change_from_issue(
            url="https://github.com/andyholst/obsidian-timestamp-utility/issues/22",
            issue_title="Random UUID helper",
            issue_body="Insert a random UUID.",
            project_root=str(tmp_path),
        )
        second = create_change_from_issue(
            url="https://github.com/andyholst/obsidian-timestamp-utility/issues/22",
            issue_title="Random UUID helper",
            issue_body="Insert a random UUID.",
            project_root=str(tmp_path),
        )
    assert first == second == "ticket22"
    # The CLI is only invoked once (the change already existed on the second call).
    assert mock_run.call_count == 1


def test_create_change_from_issue_force_rescaffolds(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        create_change_from_issue(
            url="https://github.com/andyholst/obsidian-timestamp-utility/issues/22",
            issue_title="Random UUID helper",
            issue_body="Insert a random UUID.",
            project_root=str(tmp_path),
            force=True,
        )
        create_change_from_issue(
            url="https://github.com/andyholst/obsidian-timestamp-utility/issues/22",
            issue_title="Random UUID helper",
            issue_body="Insert a random UUID.",
            project_root=str(tmp_path),
            force=True,
        )
    # With force=True the CLI is invoked on every call.
    assert mock_run.call_count == 2


def test_seeded_change_is_loadable(tmp_path):
    """A change created by create_change_from_issue must be loadable by load_change()."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        create_change_from_issue(
            url="https://github.com/andyholst/obsidian-timestamp-utility/issues/20",
            issue_title="Implement Current TimeStamp as UUID",
            issue_body="We need a UUID v7 insert command.",
            project_root=str(tmp_path),
        )
    loaded = load_change("ticket20", project_root=str(tmp_path))
    assert loaded["url"] == "openspec:ticket20"
    assert "Implement Current TimeStamp" in loaded["ticket_content"]
    assert "We need a UUID v7" in loaded["ticket_content"]
