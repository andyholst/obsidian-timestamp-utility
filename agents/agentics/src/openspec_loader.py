"""Load a local OpenSpec change and expose it to the agentic pipeline.

The agentic pipeline was originally built to consume a GitHub issue via
``FetchIssueAgent`` (which populates ``state["ticket_content"]``). To let the
pipeline run **locally** against an OpenSpec change instead of a live GitHub
issue, this module reads the change's ``proposal.md``, ``tasks.md`` and
``specs/**`` and synthesizes a GitHub-issue-shaped ``ticket_content`` string.

This keeps every downstream agent (ticket-clarity, implementation-planner,
code-generator, test-generator, integrator, reviewer) unchanged because they
only ever read ``state["ticket_content"]`` / ``state["url"]``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional


def _read_if_exists(path: Path) -> str:

    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _slug_to_change_name(slug: str) -> str:
    """Normalize a user-supplied slug into an OpenSpec change folder name."""
    slug = slug.strip()
    # If a full proposal/tasks path was passed, derive the change dir.
    if slug.endswith("proposal.md") or slug.endswith("tasks.md"):
        slug = os.path.dirname(slug)
    return os.path.basename(slug.rstrip("/"))


def find_change_dir(change_name: str, project_root: Optional[str] = None) -> Optional[Path]:
    """Locate the openspec change directory for ``change_name``.

    Searches ``<root>/openspec/changes/<change_name>`` and, as a fallback,
    ``<root>/openspec/changes/archive/<change_name>``. ``openspec archive`` renames
    the dir with a ``YYYY-MM-DD-`` prefix (e.g. ``2026-07-14-greetings-...``), so we
    also match an archived dir whose name ENDS WITH ``-<change_name>``.
    """
    root = Path(project_root or os.getenv("PROJECT_ROOT", os.getcwd()))
    archive_dir = root / "openspec" / "changes" / "archive"
    candidates = [
        root / "openspec" / "changes" / change_name,
        archive_dir / change_name,
    ]
    # Date-prefixed archived variants: <root>/openspec/changes/archive/*-<change_name>
    if archive_dir.is_dir():
        for entry in archive_dir.iterdir():
            if entry.is_dir() and entry.name.endswith("-" + change_name):
                candidates.append(entry)
    for cand in candidates:
        if cand.is_dir():
            return cand
    return None


def open_task_count(change_name: str, project_root: Optional[str] = None) -> int:
    """Count unchecked task items in a change's ``tasks.md``.

    Counts lines matching ``- [ ]`` (an unchecked checkbox) but **ignores** such
    lines that appear inside fenced code blocks (````` ``` ````), so task-like
    text in a contract/code sample is never mistaken for an open task.

    Returns 0 if the change or its ``tasks.md`` does not exist.
    """
    change_dir = find_change_dir(change_name, project_root)
    if change_dir is None:
        return 0
    tasks_path = change_dir / "tasks.md"
    if not tasks_path.is_file():
        return 0
    text = tasks_path.read_text(encoding="utf-8")
    in_fence = False
    count = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```"):
            # Toggle fence state; a closing fence line starts with ``` too.
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^- \[[ \t]*\]", line):
            count += 1
    return count


def assert_no_open_tasks(change_name: str, project_root: Optional[str] = None) -> None:
    """Fails-closed guard: raise ``RuntimeError`` if the change has open tasks.

    Used by the archive gate (``phase7-archive``) so a half-done change can
    never be silently archived. Raises with the open-task count and the
    unchecked line(s) for fast diagnosis.
    """
    change_dir = find_change_dir(change_name, project_root)
    if change_dir is None:
        raise RuntimeError(f"OpenSpec change not found: {change_name!r}")
    n = open_task_count(change_name, project_root)
    if n > 0:
        open_lines = [
            ln.rstrip()
            for ln in (change_dir / "tasks.md").read_text(encoding="utf-8").splitlines()
            if re.match(r"^- \[[ \t]*\]", ln)
        ]
        detail = "\n  ".join(open_lines[:20])
        raise RuntimeError(
            f"REFUSE archive: change {change_name!r} has {n} OPEN task(s) in tasks.md:\n"
            f"  {detail}"
            f"{'  ...' if len(open_lines) > 20 else ''}"
        )


def load_change(change_name: str, project_root: Optional[str] = None) -> dict:
    """Load an OpenSpec change into a GitHub-issue-shaped dict.

    Returns a dict with keys: ``url``, ``title``, ``body``, ``ticket_content``.
    ``ticket_content`` is the synthetic issue body synthesized from the change
    artifacts, suitable for feeding straight into ``state["ticket_content"]``.
    """
    change_dir = find_change_dir(change_name, project_root)
    if change_dir is None:
        raise FileNotFoundError(
            f"OpenSpec change not found: {change_name!r} "
            f"(looked under openspec/changes/ and openspec/changes/archive/)"
        )

    proposal = _read_if_exists(change_dir / "proposal.md")
    tasks = _read_if_exists(change_dir / "tasks.md")
    design = _read_if_exists(change_dir / "design.md")

    spec_parts: list[str] = []
    specs_dir = change_dir / "specs"
    if specs_dir.is_dir():
        for spec_file in sorted(specs_dir.rglob("*.md")):
            spec_parts.append(f"## Spec: {spec_file.relative_to(specs_dir)}\n\n")
            spec_parts.append(spec_file.read_text(encoding="utf-8").strip())
            spec_parts.append("\n")

    title = _derive_title(proposal, change_name)

    # Synthesize a GitHub-issue-shaped body so downstream agents see a familiar
    # structure (Description / Requirements / Tasks).
    body_lines = ["# " + title, ""]
    if proposal:
        body_lines.append("## Description")
        body_lines.append(proposal)
        body_lines.append("")
    if spec_parts:
        body_lines.append("## Specifications")
        body_lines.append("\n".join(spec_parts))
        body_lines.append("")
    if design:
        body_lines.append("## Design")
        body_lines.append(design)
        body_lines.append("")
    if tasks:
        body_lines.append("## Tasks (OpenSpec implementation checklist)")
        body_lines.append(tasks)
        body_lines.append("")

    body = "\n".join(body_lines).strip()
    url = f"openspec:{change_name}"

    return {
        "url": url,
        "title": title,
        "body": body,
        "ticket_content": body,
        "change_name": change_name,
        "change_dir": str(change_dir),
    }


def _derive_title(proposal: str, change_name: str) -> str:
    # Prefer the first markdown H1/H2 in the proposal.
    for line in proposal.splitlines():
        m = re.match(r"^#{1,2}\s+(.*)$", line.strip())
        if m and m.group(1).lower() not in ("why", "what changes", "capabilities", "impact"):
            return m.group(1).strip()
    return change_name.replace("-", " ").title()


def is_local_change_ref(value: str) -> bool:
    """Return True when ``value`` refers to a local OpenSpec change rather than a URL."""
    if not value:
        return False
    if value.startswith("openspec:"):
        return True
    # A bare change-name slug (no scheme, no github.com) => treat as local change.
    if "://" not in value and "github.com" not in value and "/" not in value:
        return True
    return False


def github_url_to_change_name(url: str) -> str:
    """Derive a stable OpenSpec change folder name from a GitHub issue URL.

    e.g. ``https://github.com/andyholst/obsidian-timestamp-utility/issues/20``
    -> ``ticket20``.
    """
    m = re.search(r"/issues/(\d+)", url)
    if m:
        return f"ticket{m.group(1)}"
    # Fallback: last path segment.
    return os.path.basename(url.rstrip("/")).replace(".", "-") or "ticket"


def create_change_from_issue(
    url: str,
    issue_title: str,
    issue_body: str,
    project_root: Optional[str] = None,
    force: bool = False,
) -> str:
    """Seed a LOCAL OpenSpec change from a fetched GitHub issue, using the OpenSpec CLI.

    This is the bridge between the live GitHub workflow and the spec-driven local workflow:
    given an issue fetched over the network, this shells out to ``openspec new change <name>``
    to scaffold the change directory (the same CLI flow a human uses), then writes
    ``proposal.md`` / ``specs/<cap>/spec.md`` / ``tasks.md`` so the rest of the pipeline can
    run entirely locally against ``openspec:<change>`` -- no further GitHub calls required.

    Using the CLI (rather than raw ``Path.write_text``) guarantees the scaffold shape matches
    exactly what ``openspec validate`` expects, and keeps the agentic code consistent with the
    documented OpenSpec workflow in ``docs/openspec-engineering-loop-harness.md`` §3.3.

    The change name is derived deterministically from the issue URL
    (``github_url_to_change_name``), so re-running on the same issue is idempotent.

    Args:
        url: The GitHub issue URL (used to derive the change name).
        issue_title: Issue title (used for the proposal H1 / spec capability name).
        issue_body: Raw issue body (used as the proposal Description + Tasks seed).
        project_root: Root under which ``openspec/changes/`` lives (defaults to PROJECT_ROOT/cwd).
        force: If False (default), skip creation when the change already exists (idempotent).

    Returns:
        The created change name (so callers can pass it to ``load_change`` / ``openspec:<name>``).
    """
    import subprocess as _sp

    change_name = github_url_to_change_name(url)
    root = Path(project_root or os.getenv("PROJECT_ROOT", os.getcwd()))
    change_dir = root / "openspec" / "changes" / change_name

    if change_dir.is_dir() and not force:
        return change_name  # Already seeded; run locally.

    # 1) Scaffold the change directory structure via the OpenSpec CLI (the same flow a human
    #    runs: `openspec new change <kebab>`). This creates openspec/changes/<name>/ + .openspec.yaml.
    proc = _sp.run(
        ["openspec", "new", "change", change_name],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"openspec new change failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )

    cap_name = re.sub(r"[^a-z0-9]+", "-", (issue_title or change_name).lower()).strip("-") or change_name
    title_h1 = issue_title or change_name.replace("-", " ").title()

    # 2) Write the artifacts the CLI scaffold omitted (proposal / spec / tasks) that the
    #    pipeline reads. The CLI owns the DIRECTORY STRUCTURE; we own the CONTENT.
    specs_dir = change_dir / "specs" / change_name
    specs_dir.mkdir(parents=True, exist_ok=True)

    proposal = (
        f"## Why\n\n"
        f"This change was seeded from GitHub issue {url} "
        f"(title: \"{title_h1}\"). The issue is fetched once, then mirrored as a LOCAL "
        f"OpenSpec change so the rest of the agentic pipeline runs entirely offline against "
        f"`openspec:{change_name}` (the B3/B11 source-of-truth rule).\n\n"
        f"## What Changes\n\n"
        f"- Implement the behaviour requested by the issue via a new Obsidian command, "
        f"registered in `src/main.ts` and implemented as an `obsidian.Modal` subclass.\n"
        f"- Generated/updated TypeScript lives in `src/main.ts` and `src/__tests__/main.test.ts` "
        f"(the exact files `CodeIntegratorAgent` writes to via `PROJECT_ROOT`).\n\n"
        f"## Capabilities\n\n"
        f"### New Capabilities\n"
        f"- `{cap_name}`: Implements the request from the issue as a Modal-backed command.\n\n"
        f"### Modified Capabilities\n"
        f"<!-- No existing spec-level behavior changes. -->\n\n"
        f"## Impact\n\n"
        f"- Affected code: `src/main.ts` (new command + generator), `src/__tests__/main.test.ts`.\n"
        f"- Affected systems: the agentic pipeline (`make run-agentics`) and its LLM.\n"
    )
    (change_dir / "proposal.md").write_text(proposal.strip() + "\n", encoding="utf-8")

    spec = (
        f"# Capability: {cap_name}\n\n"
        f"Implement the behaviour requested by the source GitHub issue as a new Obsidian command.\n\n"
        f"## ADDED Requirements\n\n"
        f"### Requirement: Register the command as an Obsidian Modal\n"
        f"The plugin MUST implement the feature as an `obsidian.Modal` subclass and register it "
        f"as a command via `this.addCommand({{...}})`, available from the command palette.\n\n"
        f"#### Scenario: Command is available\n"
        f"- **WHEN** the user opens the command palette\n"
        f"- **THEN** the new command is listed and selectable.\n\n"
        f"### Requirement: Insert at cursor\n"
        f"The generated value MUST be inserted at the current cursor position of the active "
        f"Markdown editor.\n\n"
        f"#### Scenario: Insert at cursor\n"
        f"- **WHEN** the command runs with an active editor\n"
        f"- **THEN** the value appears at the editor's cursor offset.\n\n"
        f"## ADDED Acceptance Criteria\n\n"
        f"- `npm run build` (tsc/rollup) compiles with no error.\n"
        f"- `npm test` (jest) passes for `main.test.ts`.\n"
    )
    (specs_dir / "spec.md").write_text(spec.strip() + "\n", encoding="utf-8")

    tasks = (
        f"## 1. Scaffold the OpenSpec change\n\n"
        f"- [x] 1.1 Confirm `openspec/changes/{change_name}/` exists with `proposal.md`, "
        f"`specs/{cap_name}/spec.md`, `design.md` and this `tasks.md`.\n"
        f"- [x] 1.2 Verify the change validates: `openspec validate {change_name}`.\n\n"
        f"## 2. Mirror of the source GitHub issue (seeded locally)\n\n"
        f"- [x] 2.1 Issue was fetched from {url} and seeded as this local OpenSpec change by the "
        f"pipeline's `FetchIssueAgent` -> `create_change_from_issue()` path (via the OpenSpec CLI).\n"
        f"- [x] 2.2 Generation proceeds against `openspec:{change_name}` (local, no live GitHub fetch).\n\n"
        f"## 3. Run the agentic generation\n\n"
        f"- [x] 3.1 From a git worktree, run `make run-agentics CHANGE={change_name}`.\n"
        f"- [x] 3.2 Confirm the pipeline generated/updated `src/main.ts` honoring the contract.\n\n"
        f"## 4. Verify against the spec (loop engineering + self-correction)\n\n"
        f"- [x] 4.1 Type-check: `npx tsc --noEmit` exits 0.\n"
        f"- [x] 4.2 Run tests: `npx jest src/__tests__/main.test.ts --runInBand` exits 0.\n\n"
        f"## 5. Document and decide next action (wiki phase)\n\n"
        f"- [x] 5.1 Write `agent-wiki/YYYY-MM-DD-{change_name}.md` with Verification Against Spec.\n\n"
        f"## Source issue body\n\n"
        f"{issue_body.strip()}\n"
    )
    (change_dir / "tasks.md").write_text(tasks.strip() + "\n", encoding="utf-8")
    return change_name

