"""Shared helper for B3-safe e2e pipeline runs.

B3 requires that e2e tests run the agentic pipeline into an ISOLATED temp dir and
NEVER write generated TypeScript into the agentics SOURCE tree (`agents/agentics/src`,
which the integration container mounts at `/app/src` with `PROJECT_ROOT=/app`).

Running the pipeline IN-PROCESS (``from src.agentics import AgenticsApp; app.process_issue``)
captures the container's ``PROJECT_ROOT=/app`` and pollutes ``agents/agentics/src``. This
helper instead spawns the pipeline as a SUBPROCESS with ``PROJECT_ROOT`` forced to a freshly
created temp dir, mirroring ``make run-agentics`` (which is clean). The subprocess reads
``PROJECT_ROOT`` at agent ``__init__`` time, so the override is honored.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile


_MODAL_RE = re.compile(r"class\s+\w*Modal\b.*?extends\s+obsidian\.Modal", re.DOTALL)
_ADDCOMMAND_RE = re.compile(r"this\.addCommand\s*\(\s*\{", re.DOTALL)


def _repo_root() -> str:
    """Resolve the repo root regardless of CWD / container mount layout.

    In the integration/e2e container ``__file__`` is under ``/app/tests/integration/``
    (only ``/app/src`` + ``/app/tests`` are mounted there); the real repo (with
    ``openspec/``) is mounted at ``/project`` as a SEPARATE (sibling) mount, so a naive
    walk-up from ``/app`` can never reach ``/project`` and ``git rev-parse`` from ``/app``
    fails (not a git worktree). We therefore check git toplevel AND probe the candidate
    roots (walk-up + the well-known container mount points ``/project``, ``/app``, cwd)
    and return the first one that actually contains ``openspec/changes``.
    """
    import subprocess as _sp

    here = os.path.dirname(os.path.abspath(__file__))
    # (1) git toplevel (works where __file__ sits inside the git worktree)
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


def make_seeded_project_root(prefix: str = "test_project_") -> str:
    """Create an ISOLATED temp PROJECT_ROOT seeded with the real plugin files.

    Pipeline integration tests (e.g. the composable-workflow / post-test-runner
    integration suites) run the full agentic pipeline — including the jest test
    phase — against ``PROJECT_ROOT``. If that dir is empty, ``CodeExtractor`` finds
    no ``src/__tests__/main.test.ts`` and jest runs 0 tests, so the
    "test count must grow" check fails (``TestRecoveryNeeded``). Seeding the temp
    dir with the real ``src/`` + build config makes the pipeline operate against a
    valid baseline, exactly like ``run_pipeline_isolated`` does for the e2e gates.

    NOTE: the plugin's TypeScript test scaffold (``src/__tests__/main.test.ts``) must
    be reachable for the seeded dir to be useful for the jest phase. In the
    integration container ``/app/src`` is overmounted by the Python agentics source
    and ``/project`` is not mounted, so the TS scaffold is unreachable there — callers
    should ``skipif`` the jest-dependent tests when it is absent (B17: live tests skip
    cleanly). Returns the temp dir path regardless; use ``plugin_ts_tests_present`` to
    check availability.
    """
    root = _repo_root()
    project_dir = tempfile.mkdtemp(prefix=prefix)
    real_src = os.path.join(root, "src")
    os.makedirs(os.path.join(project_dir, "src"), exist_ok=True)
    if os.path.isdir(real_src):
        shutil.copytree(real_src, os.path.join(project_dir, "src"), dirs_exist_ok=True)
    for fn in ("package.json", "tsconfig.json", "jest.config.js", "manifest.json"):
        src_f = os.path.join(root, fn)
        if os.path.isfile(src_f):
            shutil.copy2(src_f, os.path.join(project_dir, fn))
    return project_dir


def plugin_ts_tests_present(project_root: str) -> bool:
    """True when the plugin's TypeScript jest tests are available under project_root.

    Used by pipeline integration tests to skip cleanly (B17) when the TS scaffold is
    not mounted in the integration container (it is shadowed by the Python source
    mount at /app/src and /project is not mounted).
    """
    return os.path.isfile(
        os.path.join(project_root, "src", "__tests__", "main.test.ts")
    )


def run_pipeline_isolated(change: str, issue_url: str | None = None) -> dict:
    """Run the agentic pipeline in a SUBPROCESS into an isolated temp dir.

    Returns a dict with keys:
      - ``generated_code``: contents of ``<tmp>/src/main.ts`` (or pipeline stdout)
      - ``generated_tests``: contents of ``<tmp>/src/__tests__/main.test.ts``
      - ``project_dir``: the isolated temp dir (PROJECT_ROOT)
      - ``returncode``: subprocess exit code
      - ``stderr``: captured stderr (for debugging)

    B3 guarantee: generated TS can ONLY land under ``project_dir``. The agentics source
    tree (``/app/src`` / ``agents/agentics/src``) is never written to.
    """
    if not os.getenv("LLAMA_HOST") and not os.getenv("LLAMA_HOST"):
        raise RuntimeError("LLAMA_HOST not set -- isolated pipeline run needs a real LLM server")

    root = _repo_root()
    real_src = os.path.join(root, "src")
    project_dir = tempfile.mkdtemp(prefix=f"e2e_iso_{change}_")
    os.makedirs(os.path.join(project_dir, "src"), exist_ok=True)
    if os.path.isdir(real_src):
        shutil.copytree(real_src, os.path.join(project_dir, "src"), dirs_exist_ok=True)
    for fn in ("package.json", "tsconfig.json", "jest.config.js", "manifest.json"):
        src_f = os.path.join(root, fn)
        if os.path.isfile(src_f):
            shutil.copy2(src_f, os.path.join(project_dir, fn))

    # CRITICAL (e2e stabilization): the pipeline resolves a local OpenSpec change via
    # openspec_loader.load_change(), which looks under ``<PROJECT_ROOT>/openspec/changes/<change>``.
    # The isolated temp dir has NO openspec/ tree, so without it the loader raises
    # FileNotFoundError -> empty ticket_content -> empty generation (code_len=0). Copy the
    # SPECIFIC change's directory into the temp dir so generation runs fully locally
    # (no live GitHub). This is the source-of-truth seed the pipeline reads.
    if change:
        real_change = os.path.join(root, "openspec", "changes", change)
        # Archived changes carry a YYYY-MM-DD- prefix (openspec archive renames the dir);
        # resolve via find_change_dir so the date-prefixed variant is found too (B19).
        if not os.path.isdir(real_change):
            from src.openspec_loader import find_change_dir

            found = find_change_dir(change, project_root=root)
            if found:
                real_change = str(found)
        if os.path.isdir(real_change):
            shutil.copytree(
                real_change,
                os.path.join(project_dir, "openspec", "changes", change),
                dirs_exist_ok=True,
            )

    agentics_src = os.path.normpath(
        os.path.join(_repo_root(), "agents", "agentics", "src")
    )
    # Run the pipeline module from the agentics ROOT (not the isolated temp dir) so that
    # `python -m src.agentics` resolves `src` as a namespace package. PROJECT_ROOT is still
    # forced to the isolated temp dir (below), so all generated TS lands there (B3) -- only the
    # *process cwd* differs.
    agentics_root = os.path.dirname(agentics_src)
    env = {**os.environ, "PROJECT_ROOT": project_dir, "CHANGE": change}
    if issue_url:
        env["URL"] = issue_url
    env["PYTHONPATH"] = (agentics_src + os.pathsep + os.environ.get("PYTHONPATH", "")).rstrip(os.pathsep)

    target = issue_url or f"openspec:{change}"

    proc = subprocess.run(
        [sys.executable, "-m", "src.agentics", target],
        cwd=agentics_root, capture_output=True, text=True, env=env, timeout=900,
    )

    generated_code = ""
    gen_code_path = os.path.join(project_dir, "src", "main.ts")
    if os.path.isfile(gen_code_path):
        with open(gen_code_path, "r", encoding="utf-8") as f:
            generated_code = f.read()

    generated_tests = ""
    gen_test_path = os.path.join(project_dir, "src", "__tests__", "main.test.ts")
    if os.path.isfile(gen_test_path):
        with open(gen_test_path, "r", encoding="utf-8") as f:
            generated_tests = f.read()

    # Surface why the pipeline returned non-zero without raising here (caller decides).
    if proc.returncode != 0:
        print("PIPELINE STDERR:\n", proc.stderr[-4000:])
    # Debug aid: show project_dir, exit code, and what was actually generated.
    print(
        f"[run_pipeline_isolated] project_dir={project_dir} rc={proc.returncode} "
        f"code_len={len(generated_code)} test_len={len(generated_tests)}"
    )
    print(f"[run_pipeline_isolated] code head:\n{generated_code[:500]}")

    return {
        "generated_code": generated_code,
        "generated_tests": generated_tests,
        "project_dir": project_dir,
        "returncode": proc.returncode,
        "stderr": proc.stderr,
        "stdout": proc.stdout,
    }


def assert_modal_wired(generated_code: str):
    """B2: generated TS must contain a Modal subclass registered via this.addCommand."""
    assert generated_code, "No generated code collected from the isolated run"
    assert _MODAL_RE.search(generated_code), (
        "Generated TS has no `obsidian.Modal` subclass -- the change's modal task was not honored."
    )
    assert _ADDCOMMAND_RE.search(generated_code), (
        "Generated TS has no `this.addCommand({` -- the modal is not registered as a command."
    )
