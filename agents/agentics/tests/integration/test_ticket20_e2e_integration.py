"""
E2E integration test for GitHub issue #20 using full agentics workflow.
Tests real GitHub API fetch, full workflow execution, and output assertions.
"""

import pytest
import os
import re
from pathlib import Path

import asyncio

from src.agentics import AgenticsApp
from src.config import AgenticsConfig


@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_e2e_ticket20(
    real_ollama_config: AgenticsConfig, temp_project_dir: str
):
    """
    Full E2E test for ticket #20:
    - Fetch real issue #20 via GitHub API (GITHUB_TOKEN)
    - Run complete agentics workflow (fetch → clarify → plan → extract → generate → validate → integrate → test → output)
    - Assert generated code/tests/state/files in temp_project_dir
    """
    if not os.getenv("GITHUB_TOKEN"):
        pytest.skip("GITHUB_TOKEN required for real GitHub API access")

    repo_owner = "andyholst"
    repo_name = "obsidian-timestamp-utility"
    issue_num = 20
    issue_url = f"https://github.com/{repo_owner}/{repo_name}/issues/{issue_num}"

    app = AgenticsApp(real_ollama_config)
    await app.initialize()

    try:
        final_state = await app.process_issue(issue_url)
    finally:
        await app.shutdown()

    # Core assertions: generated content present and substantial
    assert isinstance(final_state, dict)
    assert "generated_code" in final_state
    assert len(final_state["generated_code"]) > 100
    assert "generated_tests" in final_state
    assert len(final_state["generated_tests"]) > 100

    # No LLM artifacts (thinking tags) in outputs
    def has_thinking_tags(text: str) -> bool:
        return bool(
            re.search(r"<think>.*?</think>", text, re.DOTALL | re.IGNORECASE)
        )

    assert not has_thinking_tags(final_state["generated_code"]), (
        "Thinking tags in generated_code"
    )
    assert not has_thinking_tags(final_state["generated_tests"]), (
        "Thinking tags in generated_tests"
    )

    # Workflow state fields populated
    assert "refined_ticket" in final_state
    assert "method_name" in final_state
    assert "validation_score" in final_state
    assert "result" in final_state

    # Files generated in temp_project_dir
    temp_path = Path(temp_project_dir)
    all_files = set(temp_path.iterdir())
    initial_file = temp_path / "input.txt"
    new_files = all_files - {initial_file}
    assert len(new_files) > 0, (
        f"No new files generated in {temp_project_dir}: {list(all_files)}"
    )

    # Code/test files exist (checked recursively in src/)
    code_files = []
    for f in temp_path.rglob("*"):
        if f.suffix in {".ts", ".js", ".json"} and f != initial_file:
            code_files.append(f)
    assert len(code_files) >= 1, (
        f"No code/structure files generated: {[f.name for f in new_files]}"
    )
