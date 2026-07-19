"""OpenSpec change reference loader and validation.

Provides utilities for handling OpenSpec change references in the
agentics pipeline. A local change ref has the form ``openspec:<change-id>``
where *change-id* is the directory name under ``openspec/changes/``.
"""

import os
from pathlib import Path
from typing import Optional


def is_local_change_ref(issue_url: str) -> bool:
    """Return True if *issue_url* is a local OpenSpec change reference.

    Local change references have the form ``openspec:<change-id>`` where
    *change-id* is the directory name under ``openspec/changes/``.
    """
    if not isinstance(issue_url, str):
        return False
    prefix = "openspec:"
    if not issue_url.startswith(prefix):
        return False
    change_id = issue_url[len(prefix):].strip()
    if not change_id:
        return False
    # Check the openspec directory relative to the project root
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    changes_dir = project_root / "openspec" / "changes" / change_id
    return changes_dir.is_dir()


def get_change_id(issue_url: str) -> Optional[str]:
    """Extract the change-id from an OpenSpec reference."""
    if not is_local_change_ref(issue_url):
        return None
    return issue_url.split("openspec:", 1)[1].strip()


def get_change_tasks_file(change_id: str) -> Optional[Path]:
    """Return the path to the tasks.md file for a change, or None."""
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    tasks_file = project_root / "openspec" / "changes" / change_id / "tasks.md"
    if tasks_file.is_file():
        return tasks_file
    return None


def load_change_tasks(change_id: str) -> Optional[str]:
    """Load and return the contents of a change's tasks.md file."""
    tasks_file = get_change_tasks_file(change_id)
    if tasks_file is None:
        return None
    return tasks_file.read_text(encoding="utf-8")


def get_change_proposal(change_id: str) -> Optional[str]:
    """Load and return the proposal.md for a change."""
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    proposal_file = project_root / "openspec" / "changes" / change_id / "proposal.md"
    if proposal_file.is_file():
        return proposal_file.read_text(encoding="utf-8")
    return None
