"""Standalone, side-effect-FREE guard helpers for the e2e harness.

This module deliberately has NO import-time side effects (no PROJECT_ROOT mutation, no file
IO, no env changes) so it can be imported safely from unit tests without perturbing global
state. The e2e conftest (`tests/integration/conftest.py`) imports `_e2e_may_copy_real_src`
from here.
"""


def e2e_may_copy_real_src(project_root, real_src, agentics_src_mount):
    """B5/B6 guard predicate (pure).

    Returns True only when it is safe to rmtree+copy the real plugin `src/` into
    PROJECT_ROOT/src — i.e. when PROJECT_ROOT is an ISOLATED temp dir. Returns False when the
    destination would be the REAL committed `src/` or the agentics `src` mount, so the harness
    only ever READS those and never destructively deletes the committed baseline.
    """
    project_root = _norm(project_root)
    real_src = _norm(real_src)
    agentics_src_mount = _norm(agentics_src_mount)
    dst_src = _norm(_join(project_root, "src"))
    if dst_src == real_src:
        return False
    if dst_src == agentics_src_mount or dst_src.startswith(agentics_src_mount + _sep()):
        return False
    if project_root == agentics_src_mount or project_root.startswith(agentics_src_mount + _sep()):
        return False
    if project_root in ("/app",):
        return False
    return True


def _norm(p):
    import os

    return os.path.normpath(p)


def _join(a, b):
    import os

    return os.path.join(a, b)


def _sep():
    import os

    return os.sep
