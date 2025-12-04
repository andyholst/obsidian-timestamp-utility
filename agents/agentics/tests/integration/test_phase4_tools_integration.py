import pytest
import os
import tempfile
import shutil
from typing import Dict, Any, List
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from src.tools import ToolExecutor, read_file_tool, write_file_tool, list_files_tool


@pytest.mark.integration
class TestPhase4FileToolsIntegration:

    def setup_method(self):
        """Create temporary project directory with initial file."""
        self.temp_dir = tempfile.mkdtemp(prefix="phase4_file_tools_")
        os.environ["PROJECT_ROOT"] = self.temp_dir
        init_path = os.path.join(self.temp_dir, "initial.txt")
        with open(init_path, "w") as f:
            f.write("initial content")

    def teardown_method(self):
        """Cleanup temporary directory."""
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir)
        if "PROJECT_ROOT" in os.environ:
            del os.environ["PROJECT_ROOT"]

    def test_file_tools_tool_executor_multiple_calls(self):
        """Test ToolExecutor processing multiple file tool calls from AIMessage."""
        tools: List[BaseTool] = [read_file_tool, write_file_tool, list_files_tool]
        executor = ToolExecutor(tools)

        tool_calls = [
            {"name": "read_file_tool", "args": {"file_path": "initial.txt"}},
            {"name": "write_file_tool", "args": {"file_path": "output.txt", "content": "new content from tools"}},
            {"name": "list_files_tool", "args": {"directory": "."}}
        ]

        ai_message = AIMessage(content="Process with file tools", tool_calls=tool_calls)

        tool_results = executor.execute(ai_message)

        # Assert all tools processed
        assert len(tool_results) == 3
        assert set(tool_results.keys()) == {"read_file_tool", "write_file_tool", "list_files_tool"}

        # Assert read result
        read_result = tool_results["read_file_tool"]
        assert "initial content" in read_result

        # Assert write success
        write_result = tool_results["write_file_tool"]
        assert write_result == "Successfully wrote to output.txt"

        # Verify file was actually written
        output_path = os.path.join(self.temp_dir, "output.txt")
        assert os.path.exists(output_path)
        with open(output_path, "r") as f:
            content = f.read().strip()
            assert content == "new content from tools"

        # Assert list result includes both files
        list_result = tool_results["list_files_tool"]
        assert "initial.txt" in list_result
        assert "output.txt" in list_result

    @pytest.mark.parametrize(
        "read_path,write_content,expected_files",
        [
            ("initial.txt", "param content 1", ["initial.txt", "param1.txt"]),
            ("initial.txt", "param content 2", ["initial.txt", "param2.txt"]),
        ],
        ids=["param1", "param2"]
    )
    def test_parametrized_file_tool_sequence(self, read_path, write_content, expected_files):
        """Parametrized test for file read-write-list sequence."""
        tools: List[BaseTool] = [read_file_tool, write_file_tool, list_files_tool]
        executor = ToolExecutor(tools)

        write_path = f"param_{self.test_parametrized_file_tool_sequence.__name__}.txt"[:20]  # Unique-ish

        tool_calls = [
            {"name": "read_file_tool", "args": {"file_path": read_path}},
            {"name": "write_file_tool", "args": {"file_path": write_path, "content": write_content}},
            {"name": "list_files_tool", "args": {"directory": "."}}
        ]

        ai_message = AIMessage(content="Parametrized tools", tool_calls=tool_calls)

        tool_results = executor.execute(ai_message)

        # Assertions similar to main test
        assert len(tool_results) == 3
        assert "initial content" in tool_results["read_file_tool"]
        assert f"Successfully wrote to {write_path}" == tool_results["write_file_tool"]

        write_full_path = os.path.join(self.temp_dir, write_path)
        assert os.path.exists(write_full_path)
        with open(write_full_path, "r") as f:
            assert f.read().strip() == write_content

        list_result = tool_results["list_files_tool"]
        for file_name in expected_files:
            assert file_name in list_result