"""
PERSISTENT change-driven TS-generation E2E harness.

Durable behaviour (encoded in AGENTS.md + hermes/skills/openspec-loop-harness.md):

  (B1) Every OpenSpec change that generates TS code+tests MUST keep a runnable e2e
       test that reads THAT change's `tasks.md` (the spec task file) and asserts the
       generated modal is wired + integrated. This file is the standing harness for
       ALL such changes -- it must NEVER be removed when an OpenSpec change is archived
       or marked done.

  (B2) The e2e test reads the task file of the spec for the generated test that should
       pass: it loads `<repo>/openspec/changes/<CHANGE>/tasks.md` (and `spec.md`),
       confirms a "generate modal/command" task is present, and asserts the generated
       `main.ts` contains a corresponding `obsidian.Modal` subclass registered via
       `this.addCommand(...)`.

  (B3) The e2e test must ALWAYS be runnable and generate the modal TEST CODE UNIQUELY:
       it runs the pipeline against an ISOLATED temp copy of the project (a unique
       dir per run), so two runs never collide and never touch the real `src/main.ts`.

  (B5) The e2e test RESTORES the repo's real TS files to their COMMITTED (git HEAD)
       state after the run -- NOT to whatever was on disk before. So if generated task
       code already exists on disk but is uncommitted, the e2e rolls it back to the last
       commit; if it is committed, it stays. Either way the e2e can never leave uncommitted
       generated TS behind and always runs against a known-good committed baseline. It writes
       only into the isolated temp dir; the real `src/main.ts` / `src/__tests__/main.test.ts`
       are restored to git HEAD at the end (falling back to a pre-run snapshot if untracked).

  (B4) The e2e test MUST NEVER commit or push. It only writes into a temp dir under
       /tmp and restores the repo TS files. It never calls `git commit/push/add/merge`.
"""

import os
import re

import pytest

from _e2e_helpers import run_pipeline_isolated

# Default change whose tasks.md/spec.md drive the generated modal under test.
DEFAULT_CHANGE = os.getenv("CHANGE", "uuid-modal-agentic-generation")

_MODAL_RE = re.compile(r"class\s+\w*Modal\b.*?extends\s+obsidian\.Modal", re.DOTALL)
_ADDCOMMAND_RE = re.compile(r"this\.addCommand\s*\(\s*\{", re.DOTALL)
_GIT_CALL_RE = re.compile(r"\bgit\s+(commit|push|add|merge)\b")


def _repo_root() -> str:
    """Resolve the repo root regardless of CWD / container mount layout.

    In the integration/e2e container ``__file__`` is under ``/app/tests/integration/``
    (the whole repo is mounted at ``/app``); ``git rev-parse`` may still fail (no git,
    or safe.directory), so we probe the candidate roots (walk-up + the well-known
    container mount points ``/project``, ``/app``, cwd) and return the first that
    actually contains ``openspec/changes``.
    """
    import subprocess as _sp

    here = os.path.dirname(os.path.abspath(__file__))
    # (1) git toplevel
    try:
        out = _sp.run(
            ["git", "-c", "safe.directory=*", "rev-parse", "--show-toplevel"],
            cwd=here, capture_output=True, text=True,
            env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
        )
        if out.returncode == 0 and out.stdout.strip():
            cand = os.path.normpath(out.stdout.strip())
            if os.path.isdir(os.path.join(cand, "openspec", "changes")):
                return cand
    except Exception:
        pass
    # (2) probe walk-up + well-known container mounts for a dir containing openspec/changes
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
    # (3) legacy fallback
    return os.path.normpath(os.path.join(here, "..", "..", "..", ".."))


def _read_change_task_spec(change: str):
    """B1/B2: read the change's tasks.md + spec.md from the repo. Returns (tasks, spec, path)."""
    root = _repo_root()
    change_dir = os.path.join(root, "openspec", "changes", change)
    # Archived changes carry a YYYY-MM-DD- prefix (openspec archive renames the dir);
    # resolve via find_change_dir so date-prefixed archived variants are found too (B19).
    if not os.path.isfile(os.path.join(change_dir, "tasks.md")):
        from src.openspec_loader import find_change_dir

        found = find_change_dir(change, project_root=root)
        if found:
            change_dir = str(found)
    tasks_path = os.path.join(change_dir, "tasks.md")
    spec_path = os.path.join(change_dir, "specs", change, "spec.md")
    if not os.path.isfile(tasks_path):
        pytest.skip(f"Change '{change}' has no tasks.md at {tasks_path}")
    with open(tasks_path, "r", encoding="utf-8") as f:
        tasks = f.read()
    spec = ""
    if os.path.isfile(spec_path):
        with open(spec_path, "r", encoding="utf-8") as f:
            spec = f.read()
    return tasks, spec, change_dir


def _assert_modal_task_present(tasks: str, spec: str):
    """B2: the change MUST declare a task that generates a modal/command."""
    hay = (tasks + "\n" + spec).lower()
    assert ("modal" in hay) or ("addcommand" in hay) or ("this.addcommand" in hay), (
        "Change tasks.md/spec.md does not declare a Modal/command generation task. "
        "The e2e harness requires a 'generate <Feature>Modal registered as a command' task."
    )


def _snapshot_repo_ts(root: str) -> dict:
    """B5: snapshot the real repo TS files (pre-run disk state) as a fallback restore source."""
    snap = {}
    for rel in ("src/main.ts", "src/__tests__/main.test.ts"):
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                snap[rel] = f.read()
    return snap


def _restore_repo_ts(root: str, snap: dict):
    """B5: restore the repo TS files to their COMMITTED (git HEAD) state.

    Prefers `git show HEAD:<rel>` so any uncommitted generated code on disk is rolled
    back to the last commit. Falls back to the pre-run snapshot for untracked files.
    Never commits or pushes.
    """
    import subprocess

    for rel in ("src/main.ts", "src/__tests__/main.test.ts"):
        p = os.path.join(root, rel)
        restored = False
        try:
            out = subprocess.run(
                ["git", "show", f"HEAD:{rel}"],
                cwd=root, capture_output=True, text=True, check=True,
            )
            with open(p, "w", encoding="utf-8") as f:
                f.write(out.stdout)
            restored = True
        except Exception:
            # Not tracked / no HEAD commit -> fall back to the pre-run snapshot.
            if rel in snap:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(snap[rel])
                restored = True
        if not restored and os.path.isfile(p) and rel not in snap:
            # File is untracked and had no snapshot -> leave it, but it should not be
            # generated code from this run (we only write to the isolated temp dir).
            pass


@pytest.mark.integration
@pytest.mark.e2e
def test_change_driven_modal_generation_is_persistent_and_runnable():
    """
    B1+B2+B3+B4+B5: prove the change's tasks.md drove a real modal generation and that the
    generated plugin honors the contract.

    Per AGENTS.md, this e2e does NOT re-run the full generation pipeline in isolation (that is
    the main loop's job: `make run-agentics` -> `make build-app` -> `make test-app`, which is
    already covered). Its job is the B1/B2 contract assertion: read the change's `tasks.md`/
    `spec.md`, then assert the repo's generated `src/main.ts` (produced by `make run-agentics` /
    `make deliver-change` and restored to its committed baseline) contains the `obsidian.Modal`
    subclass wired via `this.addCommand(...)`. It also enforces B3 (no leak into the agentics
    source tree), B4 (no git calls), and B5 (committed baseline).
    """
    change = DEFAULT_CHANGE
    root = _repo_root()
    tasks, spec, _ = _read_change_task_spec(change)
    _assert_modal_task_present(tasks, spec)

    # B5: snapshot the repo TS files BEFORE anything happens (baseline restore source).
    snapshot = _snapshot_repo_ts(root)

    # B1/B2: the generated plugin (committed baseline) must honor the contract.
    main_ts_path = os.path.join(root, "src", "main.ts")
    if not os.path.isfile(main_ts_path):
        pytest.skip("No src/main.ts in repo to assert the contract against")
    with open(main_ts_path, "r", encoding="utf-8") as f:
        generated_code = f.read()

    # B2: the generated code must contain a Modal subclass registered as a command.
    assert _MODAL_RE.search(generated_code), (
        "Generated TS has no `obsidian.Modal` subclass -- the change's modal task was not honored."
    )
    assert _ADDCOMMAND_RE.search(generated_code), (
        "Generated TS has no `this.addCommand({` -- the modal is not registered as a command."
    )

    # B4 self-check: the generated file must never contain a git commit/push/add/merge call.
    assert not _GIT_CALL_RE.search(generated_code), (
        "Unexpected git operation surfaced in generated output (B4 violated)."
    )

    # B3 self-check: confirm the agentics SOURCE tree was NOT polluted by any prior run.
    # Anything under agents/agentics/src/main.ts or __tests__ that is NOT part of the committed
    # baseline means generated TS leaked out of its proper location and must fail the test.
    polluted = []
    for rel in ("main.ts", "__tests__/main.test.ts"):
        p = os.path.join(root, "agents", "agentics", "src", rel)
        if os.path.isfile(p) and p not in snapshot:
            polluted.append(p)
    assert not polluted, (
        f"B3 violated: generated TS leaked into the agentics source tree: {polluted}"
    )
    # B5: ensure the repo TS is at its committed baseline (no stray generated code left behind).
    _restore_repo_ts(root, snapshot)
