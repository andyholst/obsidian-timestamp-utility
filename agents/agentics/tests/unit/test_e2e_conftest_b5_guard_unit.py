"""
Hermetic regression test for the B5/B6 e2e harness guard.

The conftest (`tests/integration/conftest.py`) copies the REAL plugin `src/` into an ISOLATED
temp PROJECT_ROOT before the e2e run. A latent defect (now fixed) did `shutil.rmtree(_dst_src)`
on the real `src/` when PROJECT_ROOT was pointed at the real repo root — a B5/B6 violation
(it deleted the committed baseline instead of reading it).

The guard is now a pure, testable predicate `_e2e_may_copy_real_src(project_root, real_src,
agentics_src_mount)`. This test asserts it returns False (do NOT copy/delete) for the dangerous
cases and True only for an isolated temp dir.
"""

import os

from tests.integration._e2e_guard import e2e_may_copy_real_src as _e2e_may_copy_real_src

_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", "..", "..", ".."))
_REAL_SRC = os.path.join(_REPO, "src")
_AGENTICS_SRC = os.path.normpath(os.path.join(_HERE, "..", "..", "src"))


def test_guard_refuses_real_repo_root():
    """Pointing PROJECT_ROOT at the real repo must NOT allow copying/deleting real src/."""
    assert _e2e_may_copy_real_src(_REPO, _REAL_SRC, _AGENTICS_SRC) is False


def test_guard_refuses_real_src_exactly():
    """PROJECT_ROOT == real repo ROOT (so dst src === real src) is refused."""
    assert _e2e_may_copy_real_src(_REPO, _REAL_SRC, _AGENTICS_SRC) is False


def test_guard_refuses_agentics_mount():
    """PROJECT_ROOT at the agentics src mount is refused (would pollute agent source)."""
    assert _e2e_may_copy_real_src(_AGENTICS_SRC, _REAL_SRC, _AGENTICS_SRC) is False


def test_guard_refuses_app_container():
    """PROJECT_ROOT == /app (Dagger container working dir) is refused."""
    assert _e2e_may_copy_real_src("/app", _REAL_SRC, _AGENTICS_SRC) is False


def test_guard_allows_isolated_temp_dir():
    """An isolated temp PROJECT_ROOT (e.g. /tmp/obsidian-project) IS allowed to copy."""
    assert _e2e_may_copy_real_src("/tmp/obsidian-project-xyz", _REAL_SRC, _AGENTICS_SRC) is True
