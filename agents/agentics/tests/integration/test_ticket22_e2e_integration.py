"""
E2E integration test for GitHub issue #22 using full agentics workflow.
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
async def test_full_e2e_ticket22(real_ollama_config: AgenticsConfig, temp_project_dir: str):
    """
    Full E2E test for ticket #22:
    - Fetch real issue #22 via GitHub API (GITHUB_TOKEN)
    - Run complete agentics workflow (fetch → planner → generator → integrator → etc.)
    - Assert generated code/tests/state/files in temp_project_dir
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

    # Core assertions: generated content present and substantial
    assert isinstance(final_state, dict)
    assert "generated_code" in final_state
    assert len(final_state["generated_code"]) > 100  # Reasonable minimum code length
    assert "generated_tests" in final_state
    assert len(final_state["generated_tests"]) > 100  # Reasonable minimum test length

    # No LLM artifacts (thinking tags) in outputs
    def has_thinking_tags(text: str) -> bool:
        return bool(re.search(r"<think>.*?</think>", text, re.DOTALL | re.IGNORECASE)) or \
               bool(re.search(r"<think>.*?</think>", text, re.DOTALL | re.IGNORECASE))

    assert not has_thinking_tags(final_state["generated_code"]), "Thinking tags in generated_code"
    assert not has_thinking_tags(final_state["generated_tests"]), "Thinking tags in generated_tests"

    # Files generated in temp_project_dir (beyond initial input.txt)
    temp_path = Path(temp_project_dir)
    all_files = set(temp_path.iterdir())
    initial_file = temp_path / "input.txt"
    new_files = all_files - {initial_file}
    assert len(new_files) > 0, f"No new files generated in {temp_project_dir}: {list(all_files)}"

    # Code/test files specifically generated
    code_files = [f for f in new_files if f.suffix in {".py", ".ts", ".js", ".json"}]
    assert len(code_files) >= 1, f"No code/structure files generated: {[f.name for f in new_files]}"

    # Workflow depth: history length or state complexity
    if "history" in final_state:
        assert len(final_state["history"]) > 5, "Insufficient workflow history"
    assert len(final_state) > 10, "Insufficient state fields populated"

    # Tool usage evidence
    tool_indicators = ["tool_results", "tools_used", "mcp_tools", "file_operations"]
    has_tool_results = any(indicator in final_state for indicator in tool_indicators) or \
                       any("tool" in k.lower() or "file" in k.lower() for k in final_state.keys())
    assert has_tool_results, "No evidence of tool usage/MCP operations in final_state"