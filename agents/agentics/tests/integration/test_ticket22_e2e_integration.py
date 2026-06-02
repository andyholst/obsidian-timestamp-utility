"""
E2E integration test for GitHub issue #22 using full agentics workflow.
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
async def test_full_e2e_ticket22(
    real_ollama_config: AgenticsConfig, temp_project_dir: str
):
    """
    Full E2E test for ticket #22:
    - Fetch real issue #22 via GitHub API (GITHUB_TOKEN)
    - Run complete agentics workflow
    - Assert generated code/tests/state/files
    """
    if not os.getenv("GITHUB_TOKEN"):
        pytest.skip("GITHUB_TOKEN required for real GitHub API access")

    repo_owner = "andyholst"
    repo_name = "obsidian-timestamp-utility"
    issue_num = 22
    issue_url = f"https://github.com/{repo_owner}/{repo_name}/issues/{issue_num}"

    app = AgenticsApp(real_ollama_config)
    await app.initialize()

    try:
        final_state = await app.process_issue(issue_url)
    finally:
        await app.shutdown()

    # Core assertions
    assert isinstance(final_state, dict)
    assert "generated_code" in final_state
    assert len(final_state["generated_code"]) > 100
    assert "generated_tests" in final_state
    assert len(final_state["generated_tests"]) > 100

    # No thinking tags
    def has_thinking_tags(text: str) -> bool:
        return bool(
            re.search(r"<think>.*?</think>", text, re.DOTALL | re.IGNORECASE)
        )

    assert not has_thinking_tags(final_state["generated_code"])
    assert not has_thinking_tags(final_state["generated_tests"])

    # Workflow state fields
    assert "refined_ticket" in final_state
    assert "method_name" in final_state
    assert "validation_score" in final_state
    assert "result" in final_state

    # Files generated
    temp_path = Path(temp_project_dir)
    all_files = set(temp_path.iterdir())
    initial_file = temp_path / "input.txt"
    new_files = all_files - {initial_file}
    assert len(new_files) > 0

    code_files = []
    for f in temp_path.rglob("*"):
        if f.suffix in {".ts", ".js", ".json"} and f != initial_file:
            code_files.append(f)
    assert len(code_files) >= 1
