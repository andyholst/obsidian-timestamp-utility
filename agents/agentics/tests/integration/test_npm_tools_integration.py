import pytest
import json
from typing import List
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from src.tools import ToolExecutor, npm_search_tool, npm_list_tool


@pytest.mark.integration
class TestPhase4NpmToolsIntegration:

    def test_npm_tools_tool_executor_multiple_calls(self, npm_mock_dir):
        """Test ToolExecutor processing multiple npm tool calls from AIMessage."""
        tools: List[BaseTool] = [npm_search_tool, npm_list_tool]
        executor = ToolExecutor(tools)

        tool_calls = [
            {"id": "call1", "name": "npm_search_tool", "args": {"package_name": "lodash", "limit": 3}, "type": "tool"},
            {"id": "call2", "name": "npm_list_tool", "args": {"depth": 0}, "type": "tool"}
        ]

        ai_message = AIMessage(content="Process with npm tools", tool_calls=tool_calls)

        tool_results = executor.execute(ai_message)

        # Assert all tools processed
        assert len(tool_results) == 2
        assert set(tool_results.keys()) == {"npm_search_tool", "npm_list_tool"}

        # Assert npm search result
        search_result = tool_results["npm_search_tool"]
        assert isinstance(search_result, str)
        assert search_result.strip().startswith("[")
        try:
            packages = json.loads(search_result)
            assert isinstance(packages, list)
            assert len(packages) > 0
            # At least one lodash-related package
            lodash_packages = [p for p in packages if "lodash" in p.get("name", "").lower()]
            assert len(lodash_packages) >= 1
        except json.JSONDecodeError:
            pytest.fail("npm_search_tool did not return valid JSON")

        # Assert npm list result
        list_result = tool_results["npm_list_tool"]
        assert isinstance(list_result, str)
        assert list_result.strip().startswith("{")
        try:
            pkg_data = json.loads(list_result)
            assert "dependencies" in pkg_data or "devDependencies" in pkg_data
        except json.JSONDecodeError:
            pytest.fail("npm_list_tool did not return valid JSON")

    @pytest.mark.parametrize(
        "package_name, expected_min_results",
        [
            ("react", 1),
            ("express", 1),
            ("jest", 1),
        ],
        ids=["react", "express", "jest"]
    )
    def test_parametrized_npm_search(self, package_name, expected_min_results):
        """Parametrized npm search tool tests."""
        tools: List[BaseTool] = [npm_search_tool]
        executor = ToolExecutor(tools)

        tool_calls = [
            {"id": "call1", "name": "npm_search_tool", "args": {"package_name": package_name, "limit": 5}, "type": "tool"}
        ]

        ai_message = AIMessage(content=f"Search for {package_name}", tool_calls=tool_calls)

        tool_results = executor.execute(ai_message)

        assert "npm_search_tool" in tool_results
        search_result = tool_results["npm_search_tool"]
        packages = json.loads(search_result)
        assert len(packages) >= expected_min_results
        # Package name should appear
        package_names = [p.get("name", "").lower() for p in packages]
        assert any(package_name.lower() in name for name in package_names)